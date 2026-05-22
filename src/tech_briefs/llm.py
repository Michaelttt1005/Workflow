from __future__ import annotations

import json
import os
import re
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


def build_ai_report(mode: str, candidates: list[Candidate]) -> dict:
    if not candidates:
        raise RuntimeError("No candidates fetched; refusing to generate an empty AI brief.")

    settings = LLMSettings.from_env()
    prompt = _build_prompt(mode, candidates)
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
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    report = _load_json_object(content)
    _normalize_report(report, mode, candidates)
    return report


def _build_prompt(mode: str, candidates: list[Candidate]) -> str:
    count = {"daily": "6-8", "weekly": "3-5 个主题", "alert": "1-3"}[mode]
    title = {
        "daily": "每日 AI 简报",
        "weekly": "每周 AI 深度简报",
        "alert": "重大 AI 更新提醒",
    }[mode]
    rows = [_candidate_payload(item) for item in candidates]
    return (
        f"请生成一份“{title}”。模式：{mode}。今天日期：{datetime.now(CENTRAL).strftime('%Y-%m-%d')}。\n"
        f"从候选中选择 {count} 条/主题。主题聚焦 AI、机器学习、数据科学、开发者工具、模型、推理、评测、开源框架。\n\n"
        "强制要求：\n"
        "- 必须用中文写正文，但产品名、论文名、项目名保留英文原名。\n"
        "- 每条必须引用候选里的真实 title/source/published/link/summary/reasons。\n"
        "- what 要说明它到底是什么，不要写“这是一篇新论文”这种废话。\n"
        "- purpose 要说明它解决什么问题或为什么值得看。\n"
        "- features 要提炼 2-4 个具体能力/技术点。\n"
        "- comparison 只写候选摘要中明确出现的 benchmark、速度、成本、能力对比；没有就写“暂无可信公开对比数据”。\n"
        "- who 要说明适合哪些开发者、研究者或团队。\n"
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


def _candidate_payload(candidate: Candidate) -> dict:
    return {
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


def _normalize_report(report: dict, mode: str, candidates: list[Candidate]) -> None:
    report.setdefault(
        "title",
        {"daily": "每日 AI 简报", "weekly": "每周 AI 深度简报", "alert": "重大 AI 更新提醒"}[mode],
    )
    report.setdefault("subtitle", f"{mmdd()} | AI 自动简报")
    report.setdefault("overview", "本期内容由 LLM 基于真实候选来源生成。")
    report.setdefault("checked_sources", sorted({readable_source(item.source) for item in candidates})[:20])
    report.setdefault("footer", "备注：本简报由云端自动化抓取候选后调用 LLM 生成。")

    url_to_candidate = {item.url: item for item in candidates}
    for entry in report.get("entries", []):
        link = str(entry.get("link", "")).strip()
        candidate = url_to_candidate.get(link)
        if candidate:
            entry.setdefault("score", str(candidate.score))
            entry.setdefault("source", readable_source(candidate.source))
            entry.setdefault("topic", topic_label(candidate))
            entry.setdefault("published", candidate.published_at.astimezone(CENTRAL).strftime("%m-%d %H:%M"))
        entry["link"] = link
