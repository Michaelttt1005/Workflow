from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import Candidate, chinese_summary, chinese_title, readable_source


CENTRAL = ZoneInfo("America/Chicago")


def mmdd(dt: datetime | None = None) -> str:
    value = dt or datetime.now(CENTRAL)
    return value.astimezone(CENTRAL).strftime("%m-%d")


def mmdd_hhmm(dt: datetime | None = None) -> str:
    value = dt or datetime.now(CENTRAL)
    return value.astimezone(CENTRAL).strftime("%m-%d-%H%M")


def _summary_text(candidate: Candidate) -> str:
    text = candidate.summary.strip()
    if not text:
        return "暂无足够摘要信息，请点击原始链接查看完整发布内容。"
    return text[:360]


def candidate_to_entry(candidate: Candidate) -> dict[str, str]:
    title = chinese_title(candidate)
    source = readable_source(candidate.source)
    summary = chinese_summary(candidate)
    return {
        "title": title,
        "what": summary,
        "purpose": "帮助开发者、数据科学或人工智能工程团队判断是否值得进一步阅读、试用或纳入技术储备。",
        "features": "核心信息来自官方发布、代码仓库发布说明、论文摘要或开发者博客；本快报只保留可追溯的低成本初筛结论。",
        "comparison": "若原始来源没有明确评测数据、价格或性能数据，则暂无可信公开对比数据。",
        "who": "适合关注人工智能工具、数据科学、机器学习平台、开发者基础设施和开源生态的人。",
        "link": candidate.url,
        "score": str(candidate.score),
        "source": source,
    }


def build_daily_report(candidates: list[Candidate]) -> dict:
    today = mmdd()
    selected = candidates[:8]
    return {
        "title": "每日科技快报",
        "subtitle": f"{today} | 轻量版 | 官方发布、代码仓库发布、论文与开发者生态优先",
        "overview": "本期按高可信来源、影响范围、可验证性和新颖性筛选。没有可靠公开评测的条目会明确标注暂无可信公开对比数据。",
        "checked_sources": sorted({readable_source(item.source) for item in candidates})[:16],
        "entries": [candidate_to_entry(item) for item in selected],
        "footer": "备注：本文件由云端自动化生成并通过机器人消息推送。",
    }


def build_alert_report(candidates: list[Candidate]) -> dict:
    selected = candidates[:3]
    return {
        "title": "重大科技更新提醒",
        "subtitle": f"{mmdd()} | 只包含分数达到重大更新阈值的条目",
        "overview": "以下内容触发了重大更新阈值，建议优先查看原始链接。普通营销信息和无可靠来源内容已过滤。",
        "checked_sources": sorted({readable_source(item.source) for item in candidates})[:16],
        "entries": [candidate_to_entry(item) for item in selected],
        "footer": "备注：高频雷达仅在发现重大更新时推送。",
    }


def build_weekly_report(candidates: list[Candidate]) -> dict:
    grouped: dict[str, list[Candidate]] = defaultdict(list)
    for item in candidates[:30]:
        label = theme_for(item)
        grouped[label].append(item)

    entries: list[dict[str, str]] = []
    for theme, items in list(grouped.items())[:5]:
        titles = "；".join(chinese_title(item) for item in items[:3])
        links = "\n".join(item.url for item in items[:3])
        entries.append(
            {
                "title": theme,
                "what": f"本周该主题下最值得看的更新包括：{titles}",
                "purpose": "用于判断这一方向是否正在形成新的产品能力、开源生态变化或工程实践变化。",
                "features": "横向关注能力、性能、成本、生态成熟度和采用门槛。",
                "comparison": "本周报只引用原始来源中的公开指标；缺少统一数据时标注暂无可信公开对比数据。",
                "who": "适合需要做技术选型、学习路线调整或产品/研究方向判断的人。",
                "link": links,
                "score": str(max(item.score for item in items)),
                "source": "、".join(sorted({readable_source(item.source) for item in items})[:4]),
            }
        )

    return {
        "title": "每周科技深度周报",
        "subtitle": f"{mmdd()} | 过去 7 天 | 主题式横向对比",
        "overview": "本周报聚合过去 7 天高分候选，按主题归并，而不是简单罗列新闻。",
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
