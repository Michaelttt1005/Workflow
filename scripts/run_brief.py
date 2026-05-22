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
from tech_briefs.models import is_major_alert_candidate
from tech_briefs.pdf import build_pdf
from tech_briefs.reporting import (
    build_alert_report,
    build_daily_report,
    build_weekly_report,
    mmdd,
    mmdd_hhmm,
    telegram_summary,
    validate_report,
)
from tech_briefs.scoring import score_candidates
from tech_briefs.state import SeenState
from tech_briefs.telegram import send_document, send_message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and optionally send a tech brief.")
    parser.add_argument("--mode", choices=["daily", "weekly", "alert"], required=True)
    parser.add_argument("--send", action="store_true", help="Send to Telegram.")
    parser.add_argument("--days", type=int, default=None, help="Override fetch lookback window.")
    parser.add_argument("--min-alert-score", type=int, default=7)
    return parser.parse_args()


def output_path(mode: str) -> Path:
    if mode == "daily":
        return ROOT / "output" / "daily" / f"{mmdd()}-科技快报.pdf"
    if mode == "weekly":
        return ROOT / "output" / "weekly" / f"{mmdd()}-科技深度周报.pdf"
    return ROOT / "output" / "alerts" / f"{mmdd_hhmm()}-重大科技更新提醒.pdf"


def write_json(path: Path, report: dict, candidates: list) -> None:
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "report": report,
        "candidate_count": len(candidates),
    }
    path.with_suffix(".json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def usable_candidates(candidates: list) -> list:
    return [
        item
        for item in candidates
        if item.title.strip()
        and item.url.strip().startswith(("http://", "https://"))
        and item.source.strip()
    ]


def notify_validation_failure(mode: str, errors: list[str], send: bool) -> None:
    message = f"{mode} 科技快报生成失败：内容校验未通过。\n" + "\n".join(f"- {error}" for error in errors[:8])
    print(message)
    if not send:
        return
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        send_message(token, chat_id, message)


def main() -> int:
    args = parse_args()
    ensure_dirs(ROOT)
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
        selected = new_alerts[:3]
        report = build_alert_report(selected)
    elif args.mode == "weekly":
        selected = candidates[:20]
        report = build_weekly_report(selected)
    else:
        selected = candidates[:8]
        report = build_daily_report(selected)

    validation_errors = validate_report(report, args.mode)
    if validation_errors:
        notify_validation_failure(args.mode, validation_errors, args.send)
        raise RuntimeError("Content validation failed; PDF was not generated or sent.")

    if args.mode == "alert" and args.send:
        for item in selected:
            state.remember(item, alert_sent=True)
        state.save()
    pdf_path = output_path(args.mode)
    build_pdf(report, pdf_path)
    write_json(pdf_path, report, selected)
    print(f"Generated {pdf_path}")

    if args.send:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required when --send is used.")
        send_message(token, chat_id, telegram_summary(report))
        caption = {
            "daily": f"每日科技快报 - {mmdd()}",
            "weekly": f"每周科技深度周报 - {mmdd()}",
            "alert": f"重大科技更新提醒 - {datetime.now().strftime('%m-%d %H:%M')}",
        }[args.mode]
        send_document(token, chat_id, pdf_path, caption)
        print("Telegram push sent.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
