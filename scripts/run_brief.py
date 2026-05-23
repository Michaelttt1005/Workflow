from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tech_briefs.config import ensure_dirs, load_config
from tech_briefs.fetchers import fetch_all
from tech_briefs.llm import build_ai_report
from tech_briefs.models import is_major_alert_candidate
from tech_briefs.pdf import build_pdf
from tech_briefs.reporting import (
    CENTRAL,
    mmdd,
    mmdd_hhmm,
    telegram_summary,
    validate_report,
)
from tech_briefs.scoring import score_candidates
from tech_briefs.state import SeenState
from tech_briefs.telegram import get_bot_identity, send_document, send_message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and optionally send a tech brief.")
    parser.add_argument("--mode", choices=["daily", "weekly", "alert"], required=True)
    parser.add_argument("--send", action="store_true", help="Send to Telegram.")
    parser.add_argument("--skip-if-sent", action="store_true", help="Skip daily/weekly Telegram sends already recorded for this period.")
    parser.add_argument("--days", type=int, default=None, help="Override fetch lookback window.")
    parser.add_argument("--min-alert-score", type=int, default=7)
    return parser.parse_args()


def output_path(mode: str) -> Path:
    if mode == "daily":
        return ROOT / "output" / "daily" / f"{mmdd()}-AI简报.pdf"
    if mode == "weekly":
        return ROOT / "output" / "weekly" / f"{mmdd()}-AI深度周报.pdf"
    return ROOT / "output" / "alerts" / f"{mmdd_hhmm()}-重大AI更新提醒.pdf"


def write_json(path: Path, report: dict, candidates: list) -> None:
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "report": report,
        "candidate_count": len(candidates),
    }
    path.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def brief_period(mode: str) -> str:
    now = datetime.now(CENTRAL)
    if mode == "daily":
        return now.strftime("%Y-%m-%d")
    if mode == "weekly":
        return now.strftime("%G-W%V")
    raise ValueError(f"Unsupported sent-brief mode: {mode}")


def sent_briefs_path() -> Path:
    return ROOT / "data" / "state" / "sent-briefs.json"


def load_sent_briefs() -> dict:
    path = sent_briefs_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"sent": []}


def sent_brief_key(mode: str) -> str:
    return f"{mode}:{brief_period(mode)}"


def already_sent_brief(mode: str) -> bool:
    if mode not in {"daily", "weekly"}:
        return False
    key = sent_brief_key(mode)
    return any(item.get("key") == key for item in load_sent_briefs().get("sent", []))


def remember_sent_brief(mode: str, pdf_path: Path, report: dict) -> None:
    if mode not in {"daily", "weekly"}:
        return
    data = load_sent_briefs()
    key = sent_brief_key(mode)
    records = [item for item in data.get("sent", []) if item.get("key") != key]
    records.append(
        {
            "key": key,
            "mode": mode,
            "period": brief_period(mode),
            "title": report.get("title", ""),
            "pdf": str(pdf_path.relative_to(ROOT)),
            "sent_at": datetime.utcnow().isoformat() + "Z",
        }
    )
    data["sent"] = records[-120:]
    sent_briefs_path().write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def telegram_delivery_line(label: str, payload: dict) -> str:
    result = payload.get("result") or {}
    chat = result.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    chat_tail = chat_id[-4:] if chat_id else "unknown"
    message_id = result.get("message_id", "unknown")
    chat_type = chat.get("type", "unknown")
    return f"Telegram {label} accepted: chat_type={chat_type} chat_id_tail={chat_tail} message_id={message_id}"


def telegram_bot_line(payload: dict) -> str:
    result = payload.get("result") or {}
    username = result.get("username") or "unknown"
    bot_id = str(result.get("id", ""))
    bot_tail = bot_id[-4:] if bot_id else "unknown"
    first_name = result.get("first_name") or "unknown"
    return f"Telegram bot identity: @{username} first_name={first_name} bot_id_tail={bot_tail}"


def usable_candidates(candidates: list) -> list:
    return [
        item
        for item in candidates
        if item.title.strip()
        and item.url.strip().startswith(("http://", "https://"))
        and item.source.strip()
    ]


def notify_validation_failure(mode: str, errors: list[str], send: bool) -> None:
    message = f"{mode} AI 简报生成失败：内容校验未通过。\n" + "\n".join(f"- {error}" for error in errors[:8])
    print(message)
    if not send:
        return
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        send_message(token, chat_id, message)


def build_valid_report(mode: str, selected: list, send: bool) -> dict:
    previous_report: dict | None = None
    validation_errors: list[str] | None = None

    for attempt in range(1, 4):
        report = build_ai_report(mode, selected, validation_errors, previous_report)
        validation_errors = validate_report(report, mode)
        if not validation_errors:
            if attempt > 1:
                print(f"LLM report passed validation on attempt {attempt}.")
            return report

        print(f"LLM report attempt {attempt} failed validation:")
        for error in validation_errors[:8]:
            print(f"- {error}")
        previous_report = report

    notify_validation_failure(mode, validation_errors or ["unknown validation failure"], send)
    raise RuntimeError("Content validation failed after LLM repair attempts; PDF was not generated or sent.")


def main() -> int:
    args = parse_args()
    ensure_dirs(ROOT)
    if args.skip_if_sent and args.send and already_sent_brief(args.mode):
        print(f"{args.mode} brief already sent for {brief_period(args.mode)}. Skipping duplicate Telegram push.")
        return 0

    config = load_config(ROOT / "config" / "sources.yaml")
    days = args.days or {"daily": 3, "weekly": 7, "alert": 2}[args.mode]

    candidates = fetch_all(config, days=days, github_token=os.getenv("GITHUB_TOKEN"))
    candidates = usable_candidates(score_candidates(candidates, config))
    state = SeenState(ROOT / "data" / "state" / "seen-alerts.json")

    if args.mode == "alert":
        new_alerts = [
            item
            for item in candidates
            if is_major_alert_candidate(item, args.min_alert_score) and not state.has_seen(item)
        ]
        if not new_alerts:
            print("No new major tech updates. Telegram push skipped.")
            return 0
        selected = new_alerts[:8]
    elif args.mode == "weekly":
        selected = candidates[:20]
    else:
        selected = candidates[:12]

    report = build_valid_report(args.mode, selected, args.send)

    pdf_path = output_path(args.mode)
    build_pdf(report, pdf_path)
    write_json(pdf_path, report, selected)
    print(f"Generated {pdf_path}")

    if args.send:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required when --send is used.")
        print(telegram_bot_line(get_bot_identity(token)))
        message_result = send_message(token, chat_id, telegram_summary(report))
        print(telegram_delivery_line("message", message_result))
        caption = {
            "daily": f"每日 AI 简报 - {mmdd()}",
            "weekly": f"每周 AI 深度周报 - {mmdd()}",
            "alert": f"重大 AI 更新提醒 - {datetime.now().strftime('%m-%d %H:%M')}",
        }[args.mode]
        document_result = send_document(token, chat_id, pdf_path, caption)
        print(telegram_delivery_line("document", document_result))
        print("Telegram push sent.")
        remember_sent_brief(args.mode, pdf_path, report)
        if args.mode == "alert":
            for item in selected:
                state.remember(item, alert_sent=True)
            state.save()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
