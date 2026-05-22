from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import (
    Candidate,
    audience_note,
    chinese_summary,
    chinese_title,
    comparison_note,
    feature_note,
    item_type_label,
    purpose_note,
    readable_source,
    summary_excerpt,
    topic_label,
)


CENTRAL = ZoneInfo("America/Chicago")


def mmdd(dt: datetime | None = None) -> str:
    value = dt or datetime.now(CENTRAL)
    return value.astimezone(CENTRAL).strftime("%m-%d")


def mmdd_hhmm(dt: datetime | None = None) -> str:
    value = dt or datetime.now(CENTRAL)
    return value.astimezone(CENTRAL).strftime("%m-%d-%H%M")


def candidate_to_entry(candidate: Candidate) -> dict[str, str]:
    return {
        "title": chinese_title(candidate),
        "what": chinese_summary(candidate),
        "purpose": purpose_note(candidate),
        "features": feature_note(candidate),
        "comparison": comparison_note(candidate),
        "who": audience_note(candidate),
        "link": candidate.url,
        "score": str(candidate.score),
        "source": readable_source(candidate.source),
        "type": item_type_label(candidate),
        "topic": topic_label(candidate),
        "published": candidate.published_at.astimezone(CENTRAL).strftime("%m-%d %H:%M"),
    }


def build_daily_report(candidates: list[Candidate]) -> dict:
    today = mmdd()
    selected = candidates[:8]
    return {
        "title": "每日科技快报",
        "subtitle": f"{today} | 轻量版 | 官方发布、GitHub Release、论文与开发者生态优先",
        "overview": "本期按来源可信度、影响范围、可验证性和新颖性筛选。标题保留原始产品名、项目名或论文名；解释部分用中文压缩成可行动信息。",
        "checked_sources": sorted({readable_source(item.source) for item in candidates})[:16],
        "entries": [candidate_to_entry(item) for item in selected],
        "footer": "备注：本文件由云端自动化生成，并通过机器人消息推送。",
    }


def build_alert_report(candidates: list[Candidate]) -> dict:
    selected = candidates[:3]
    return {
        "title": "重大科技更新提醒",
        "subtitle": f"{mmdd()} | 只包含达到重大更新阈值的条目",
        "overview": "以下内容触发了重大更新阈值，建议优先打开原文确认影响范围。普通营销信息和低可信来源内容已过滤。",
        "checked_sources": sorted({readable_source(item.source) for item in candidates})[:16],
        "entries": [candidate_to_entry(item) for item in selected],
        "footer": "备注：高频雷达仅在发现重大更新时推送。",
    }


def build_weekly_report(candidates: list[Candidate]) -> dict:
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for item in candidates[:30]:
        grouped[theme_for(item)].append(item)

    entries: list[dict[str, str]] = []
    for theme, items in list(grouped.items())[:5]:
        support = [
            f"{chinese_title(item)}（{readable_source(item.source)}，{item.published_at.astimezone(CENTRAL).strftime('%m-%d')}）：{summary_excerpt(item, 180)}"
            for item in items[:3]
        ]
        links = "\n".join(f"{chinese_title(item)}: {item.url}" for item in items[:3])
        comparisons = [comparison_note(item) for item in items[:2]]
        entries.append(
            {
                "title": theme,
                "what": "本周该主题下的真实支撑条目：" + "；".join(support),
                "purpose": f"判断“{theme}”方向是否出现值得调整技术选型、学习重点或产品路线的变化。",
                "features": "支撑条目来自原始标题、摘要或 release notes：" + "；".join(summary_excerpt(item, 130) for item in items[:2]),
                "comparison": "；".join(comparisons),
                "who": audience_note(items[0]),
                "link": links,
                "score": str(max(item.score for item in items)),
                "source": "、".join(sorted({readable_source(item.source) for item in items})[:4]),
                "type": "主题汇总",
                "topic": theme,
                "published": f"过去 7 天，{len(items)} 条候选",
            }
        )

    return {
        "title": "每周科技深度周报",
        "subtitle": f"{mmdd()} | 过去 7 天 | 主题式横向对比",
        "overview": "本周报聚合过去 7 天高分候选，按主题归并，保留英文产品名、项目名和论文名，并用中文说明作用、功能与对比风险。",
        "checked_sources": sorted({readable_source(item.source) for item in candidates})[:20],
        "entries": entries,
        "footer": "备注：周报优先复用同一套低成本抓取和评分逻辑。",
    }


def theme_for(candidate: Candidate) -> str:
    blob = f"{candidate.title} {candidate.summary} {candidate.source}".lower()
    if any(word in blob for word in ["cuda", "gpu", "inference", "vllm", "latency", "throughput"]):
        return "推理性能与基础设施"
    if any(word in blob for word in ["agent", "tool", "mcp", "sdk", "api"]):
        return "智能体与开发者平台"
    if any(word in blob for word in ["embedding", "rag", "retrieval", "search"]):
        return "检索增强与向量模型"
    if candidate.item_type == "paper" or "arxiv" in candidate.source.lower():
        return "重要论文与研究进展"
    if any(word in blob for word in ["model", "multimodal", "reasoning", "llm"]):
        return "新模型与模型能力"
    return "开源项目与数据科学工具"


def telegram_summary(report: dict, max_items: int = 3) -> str:
    lines = [report["title"], report.get("subtitle", ""), report.get("overview", ""), ""]
    for entry in report.get("entries", [])[:max_items]:
        lines.append(f"- {entry['title']} | {entry.get('source', '')} | {entry.get('link', '').splitlines()[0]}")
    return "\n".join(line for line in lines if line is not None).strip()


PLACEHOLDER_PHRASES = [
    "建议先看摘要、方法、实验设置",
    "快速判断这条更新是否值得继续阅读",
    "核心信息来自官方发布、代码仓库发布说明、论文摘要或开发者博客",
    "帮助开发者、数据科学或人工智能工程团队判断是否值得进一步阅读",
    "适合关注人工智能、数据科学、机器学习平台、开发者基础设施和开源生态的人",
    "当前来源没有稳定可比的公开指标时",
    "模型训练与推理能力新论文",
    "多模态与视频理解新论文",
    "机器学习研究新论文",
    "研究与工程进展",
    "未命名科技更新",
    "待补充",
    "示例",
    "模板",
    "占位",
    "TODO",
    "N/A",
]


def validate_report(report: dict, mode: str) -> list[str]:
    errors: list[str] = []
    entries = report.get("entries") or []
    min_entries = {"daily": 5, "weekly": 3, "alert": 1}[mode]
    if len(entries) < min_entries:
        errors.append(f"{mode} report has only {len(entries)} entries; expected at least {min_entries}.")

    checked_sources = report.get("checked_sources") or []
    if not checked_sources:
        errors.append("checked_sources is empty.")

    text = _report_text(report)
    for phrase in PLACEHOLDER_PHRASES:
        if phrase in text:
            errors.append(f"placeholder phrase found: {phrase}")

    if mode == "daily" and len(text) < 1800:
        errors.append("daily report text is too short to be substantive.")
    if mode == "weekly" and len(text) < 3000:
        errors.append("weekly report text is too short to be substantive.")
    if mode == "alert" and len(text) < 800:
        errors.append("alert report text is too short to be substantive.")

    for index, entry in enumerate(entries, start=1):
        for field in ("title", "what", "purpose", "features", "comparison", "who", "link", "source", "published"):
            value = str(entry.get(field, "")).strip()
            if not value:
                errors.append(f"entry {index} missing {field}.")
        link = str(entry.get("link", "")).strip()
        urls = re.findall(r"https?://\S+", link)
        if not urls or not all(url.startswith(("http://", "https://")) for url in urls):
            errors.append(f"entry {index} has no valid URL.")
        title = str(entry.get("title", "")).strip()
        if len(title) < 8 or title.endswith("新论文"):
            errors.append(f"entry {index} has generic title: {title}")

    return errors


def _report_text(value) -> str:
    if isinstance(value, dict):
        return "\n".join(_report_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_report_text(item) for item in value)
    return str(value)
