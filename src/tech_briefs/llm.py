from __future__ import annotations

import json
import os
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime

import requests

from .models import Candidate, readable_source, topic_label
from .reporting import CENTRAL, mmdd


@dataclass(frozen=True)
class LLMSettings:
    api_key: str
    base_url: str
    model: str

    @classmethod
    def from_env(cls) -> "LLMSettings":
        api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "LLM_API_KEY is required. Refusing to generate a function-template brief without a real LLM."
            )
        return cls(
            api_key=api_key,
            base_url=(os.getenv("LLM_BASE_URL") or "https://api.deepseek.com").rstrip("/"),
            model=os.getenv("LLM_MODEL") or "deepseek-chat",
        )

    @property
    def chat_completions_url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/chat/completions"


def build_ai_report(
    mode: str,
    candidates: list[Candidate],
    validation_errors: list[str] | None = None,
    previous_report: dict | None = None,
) -> dict:
    if not candidates:
        raise RuntimeError("No candidates fetched; refusing to generate an empty AI brief.")

    settings = LLMSettings.from_env()
    prompt = _build_prompt(mode, candidates, validation_errors, previous_report)
    payload = {
        "model": settings.model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个严谨的中文 AI 行业简报编辑。你必须基于输入候选源写作，"
                    "不得编造事实、链接、日期、benchmark 或价格。输出只能是合法 JSON。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    response = requests.post(
        settings.chat_completions_url,
        headers={
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=90,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"LLM request failed with HTTP {response.status_code}. "
            f"url={settings.chat_completions_url}, model={settings.model}, "
            f"body={_redact(response.text[:1200])}"
        )
    data = response.json()
    with suppress(KeyError, IndexError, TypeError):
        content = data["choices"][0]["message"]["content"]
        report = _load_json_object(content)
        _normalize_report(report, mode, candidates)
        return report
    raise RuntimeError(f"LLM response did not contain choices[0].message.content: {_redact(json.dumps(data)[:1200])}")


def _build_prompt(
    mode: str,
    candidates: list[Candidate],
    validation_errors: list[str] | None,
    previous_report: dict | None,
) -> str:
    count = {"daily": "6-8", "weekly": "6-8", "alert": "1-3"}[mode]
    title = {
        "daily": "每日 AI 简报",
        "weekly": "每周 AI 深度简报",
        "alert": "重大 AI 更新提醒",
    }[mode]
    rows = [_candidate_payload(index, item) for index, item in enumerate(candidates, start=1)]
    prompt = (
        f"请生成一份“{title}”。模式：{mode}。今天日期：{datetime.now(CENTRAL).strftime('%Y-%m-%d')}。\n"
        f"从候选中选择 {count} 条/主题。主题聚焦 AI、机器学习、数据科学、开发者工具、模型、推理、评测、开源框架。\n\n"
        "强制要求：\n"
        "- 必须用中文写正文，但产品名、论文名、项目名保留英文原名。\n"
        "- 每条必须引用候选里的真实 id/title/source/published/link/summary/reasons，并在输出里保留 candidate_id。\n"
        "- title 必须是可读标题，不要只有版本号、commit hash、短代码或“某某新论文”。GitHub release 要写出项目名和核心变更。\n"
        "- what 要说明它到底是什么，不要写“这是一篇新论文”这种废话。\n"
        "- purpose 要说明它解决什么问题或为什么值得看。\n"
        "- features 要提炼 2-4 个具体能力/技术点。\n"
        "- comparison 只写候选摘要中明确出现的 benchmark、速度、成本、能力对比；没有就写“暂无可信公开对比数据”。\n"
        "- who 要说明适合哪些开发者、研究者或团队。\n"
        f"- 每条的 what/purpose/features/comparison/who 合计至少 {_minimum_entry_chars(mode)} 个中文字符，不能只写短句。\n"
        "- link 必须是候选中的真实 URL。\n"
        "- 不要输出模板句、占位符、TODO、N/A、泛化废话。\n\n"
        "输出 JSON schema：\n"
        "{\n"
        '  "title": "每日 AI 简报 / 每周 AI 深度简报 / 重大 AI 更新提醒",\n'
        '  "subtitle": "MM-DD | 简短说明",\n'
        '  "overview": "本期 2-4 句总览",\n'
        '  "checked_sources": ["..."],\n'
        '  "entries": [\n'
        "    {\n"
        '      "candidate_id": "候选 id",\n'
        '      "title": "真实标题",\n'
        '      "what": "是什么",\n'
        '      "purpose": "主要作用",\n'
        '      "features": "核心功能",\n'
        '      "comparison": "性能/能力/成本对比或暂无可信公开对比数据",\n'
        '      "who": "适合谁",\n'
        '      "link": "https://...",\n'
        '      "score": "数字",\n'
        '      "source": "真实来源",\n'
        '      "type": "论文/官方发布/GitHub Release/产品更新",\n'
        '      "topic": "主题",\n'
        '      "published": "MM-DD HH:mm"\n'
        "    }\n"
        "  ],\n"
        '  "footer": "简短备注"\n'
        "}\n\n"
        "候选 JSON：\n"
        f"{json.dumps(rows, ensure_ascii=False, indent=2)}"
    )

    if validation_errors:
        prompt += (
            "\n\n上一次输出没有通过本地校验。请不要解释，直接返回一份完整的修正版 JSON。\n"
            "校验错误：\n"
            + "\n".join(f"- {error}" for error in validation_errors[:12])
        )
        if previous_report:
            prompt += (
                "\n\n上一次输出 JSON：\n"
                f"{json.dumps(previous_report, ensure_ascii=False, indent=2)[:12000]}"
            )

    if mode == "weekly":
        prompt += (
            "\n\n周报额外要求：\n"
            "- entries 必须至少 6 条，优先覆盖模型/论文、智能体、端侧推理、开发者平台、基础设施、开源 release。\n"
            "- overview 至少 250 个中文字符，必须做本周横向总结，不要只列清单。\n"
            "- 每条要写成深度周报风格：是什么、为什么这周值得看、核心变化、对比判断、适合采用的人群都要展开。\n"
            "- 整份报告正文必须超过 3500 个中文字符，否则会被本地校验拒绝并不会发送 Telegram。\n"
        )

    return prompt


def _minimum_entry_chars(mode: str) -> int:
    return {"daily": 260, "weekly": 520, "alert": 320}[mode]


def _candidate_payload(index: int, candidate: Candidate) -> dict:
    return {
        "id": str(index),
        "title": candidate.title,
        "url": candidate.url,
        "source": readable_source(candidate.source),
        "published": candidate.published_at.astimezone(CENTRAL).strftime("%Y-%m-%d %H:%M"),
        "summary": candidate.summary[:1600],
        "item_type": candidate.item_type,
        "topic_hint": topic_label(candidate),
        "score": candidate.score,
        "reasons": candidate.reasons,
    }


def _load_json_object(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _redact(text: str) -> str:
    return re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "sk-***", text)


def _normalize_report(report: dict, mode: str, candidates: list[Candidate]) -> None:
    report.setdefault(
        "title",
        {"daily": "每日 AI 简报", "weekly": "每周 AI 深度简报", "alert": "重大 AI 更新提醒"}[mode],
    )
    report.setdefault("subtitle", f"{mmdd()} | AI 自动简报")
    report.setdefault("overview", "本期内容由 LLM 基于真实候选来源生成。")
    report.setdefault("checked_sources", sorted({readable_source(item.source) for item in candidates})[:20])
    report.setdefault("footer", "备注：本简报由云端自动化抓取候选后调用 LLM 生成。")

    if not isinstance(report.get("entries"), list):
        report["entries"] = []

    url_to_candidate = {item.url.strip(): item for item in candidates}
    id_to_candidate = {str(index): item for index, item in enumerate(candidates, start=1)}
    normalized_entries: list[dict] = []
    for raw_entry in report.get("entries", []):
        if not isinstance(raw_entry, dict):
            continue
        entry = raw_entry
        for key in (
            "candidate_id",
            "title",
            "what",
            "purpose",
            "features",
            "comparison",
            "who",
            "link",
            "score",
            "source",
            "type",
            "topic",
            "published",
        ):
            entry[key] = _stringify(entry.get(key, ""))

        link = entry["link"].strip()
        candidate = id_to_candidate.get(entry["candidate_id"].strip()) or url_to_candidate.get(link)
        if not candidate:
            candidate = _match_candidate_by_title(entry["title"], candidates)
        if candidate:
            entry["candidate_id"] = str(candidates.index(candidate) + 1)
            entry["link"] = candidate.url
            entry["score"] = str(candidate.score)
            entry["source"] = readable_source(candidate.source)
            entry["topic"] = topic_label(candidate)
            entry["published"] = candidate.published_at.astimezone(CENTRAL).strftime("%m-%d %H:%M")
            entry["type"] = _entry_type(candidate)
            if _generic_title(entry["title"]):
                entry["title"] = candidate.title
        else:
            entry["link"] = link
        normalized_entries.append(entry)

    report["entries"] = normalized_entries


def _stringify(value: object) -> str:
    if isinstance(value, list):
        return "；".join(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, dict):
        return "；".join(f"{key}: {val}" for key, val in value.items())
    return str(value or "").strip()


def _match_candidate_by_title(title: str, candidates: list[Candidate]) -> Candidate | None:
    normalized = " ".join(title.lower().split())
    if not normalized:
        return None
    for candidate in candidates:
        candidate_title = " ".join(candidate.title.lower().split())
        if normalized == candidate_title:
            return candidate
    return None


def _generic_title(title: str) -> bool:
    value = title.strip().lower()
    if len(value) < 8:
        return True
    if value.endswith("新论文"):
        return True
    if re.fullmatch(r"[a-f0-9]{5,16}", value):
        return True
    if re.fullmatch(r"v?\d[\w.\-+]*", value):
        return True
    return False


def _entry_type(candidate: Candidate) -> str:
    if candidate.item_type == "paper":
        return "论文"
    if candidate.item_type == "github_release":
        return "GitHub Release"
    if candidate.item_type == "official":
        return "官方发布"
    return "产品更新"
