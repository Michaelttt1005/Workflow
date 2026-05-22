from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import (
    Candidate,
    chinese_summary,
    chinese_title,
    comparison_note,
    item_type_label,
    readable_source,
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
        "purpose": "快速判断这条更新是否值得继续阅读、试用、收藏或纳入技术储备。",
        "features": _feature_note(candidate),
        "comparison": comparison_note(candidate),
        "who": "适合关注人工智能、数据科学、机器学习平台、开发者基础设施和开源生态的人。",
        "link": candidate.url,
        "score": str(candidate.score),
        "source": readable_source(candidate.source),
        "type": item_type_label(candidate),
        "topic": topic_label(candidate),
        "published": candidate.published_at.astimezone(CENTRAL).strftime("%m-%d %H:%M"),
    }


def _feature_note(candidate: Candidate) -> str:
    if candidate.item_type == "github_release":
        return "重点看新功能、破坏性变更、迁移成本、依赖升级、性能变化和已修复问题。"
    if candidate.item_type == "paper" or "arxiv" in candidate.source.lower():
        return "重点看问题定义、方法差异、实验设置、公开数据、代码可用性和失败案例。"
    return "重点看功能入口、适用地区、价格或接口变化、调用限制、发布时间表和官方示例。"


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
        titles = "；".join(chinese_title(item) for item in items[:3])
        links = "\n".join(item.url for item in items[:3])
        entries.append(
            {
                "title": theme,
                "what": f"本周该主题下最值得看的更新包括：{titles}",
                "purpose": "用于判断这一方向是否正在形成新的产品能力、开源生态变化或工程实践变化。",
                "features": "横向关注能力、性能、成本、生态成熟度、迁移成本和采用门槛。",
                "comparison": "周报只引用原始来源里的公开指标；没有统一数据时，标注暂无可信公开对比数据。",
                "who": "适合需要做技术选型、学习路线调整或产品/研究方向判断的人。",
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
    lines = [report["title"], report.get("subtitle", ""), ""]
    for entry in report.get("entries", [])[:max_items]:
        lines.append(f"- {entry['title']}")
    return "\n".join(line for line in lines if line is not None).strip()
