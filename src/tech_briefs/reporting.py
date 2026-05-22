from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo


CENTRAL = ZoneInfo("America/Chicago")


def mmdd(dt: datetime | None = None) -> str:
    value = dt or datetime.now(CENTRAL)
    return value.astimezone(CENTRAL).strftime("%m-%d")


def mmdd_hhmm(dt: datetime | None = None) -> str:
    value = dt or datetime.now(CENTRAL)
    return value.astimezone(CENTRAL).strftime("%m-%d-%H%M")


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
    "这是一篇新论文",
    "这是一篇来自",
    "新的科技内容",
    "建议通过原文确认",
    "原始摘要/发布说明中的具体线索",
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
    if "AI" not in str(report.get("title", "")) and "人工智能" not in str(report.get("title", "")):
        errors.append("report title must clearly identify this as an AI brief.")

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
        body = "\n".join(str(entry.get(field, "")) for field in ("what", "purpose", "features", "comparison", "who"))
        if len(body) < 220:
            errors.append(f"entry {index} body is too thin to be an AI-written brief.")

    return errors


def _report_text(value) -> str:
    if isinstance(value, dict):
        return "\n".join(_report_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_report_text(item) for item in value)
    return str(value)
