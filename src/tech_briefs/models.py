from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class Candidate:
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str = ""
    item_type: str = "news"
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return canonical_key(self.url, self.title)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.astimezone(timezone.utc).isoformat(),
            "summary": self.summary,
            "item_type": self.item_type,
            "score": self.score,
            "reasons": self.reasons,
        }


def canonical_key(url: str, title: str) -> str:
    normalized_url = (url or "").split("?")[0].split("#")[0].strip().lower()
    normalized_title = " ".join((title or "").lower().split())
    return f"{normalized_url}|{normalized_title[:120]}"


def readable_source(source: str) -> str:
    if source.startswith("arXiv"):
        return "arXiv 论文预印本"
    if source.startswith("GitHub Release:"):
        return "GitHub Release"

    replacements = {
        "OpenAI News": "OpenAI 官方新闻",
        "Anthropic News": "Anthropic 官方新闻",
        "Google DeepMind Blog": "Google DeepMind 博客",
        "Google Developers Blog": "Google Developers Blog",
        "Meta AI Blog": "Meta AI Blog",
        "Microsoft Research Blog": "Microsoft Research Blog",
        "NVIDIA Developer Blog": "NVIDIA Developer Blog",
        "PyTorch Blog": "PyTorch Blog",
        "TensorFlow Blog": "TensorFlow Blog",
        "Hugging Face Blog": "Hugging Face Blog",
    }
    return replacements.get(source, source)


def display_title(candidate: Candidate) -> str:
    title = candidate.title.strip() or "未命名科技更新"
    if candidate.item_type == "github_release":
        repo = candidate.raw.get("repo") or candidate.source.split(":", 1)[-1].strip()
        if title.lower().startswith(repo.lower()):
            return title
        return f"{repo} {title}"
    return title


def chinese_title(candidate: Candidate) -> str:
    return display_title(candidate)


def item_type_label(candidate: Candidate) -> str:
    if candidate.item_type == "github_release":
        return "开源版本发布"
    if candidate.item_type == "paper" or "arxiv" in candidate.source.lower():
        return "论文"
    return "产品/技术更新"


def topic_label(candidate: Candidate) -> str:
    blob = f"{candidate.title} {candidate.summary} {candidate.source}".lower()
    if any(word in blob for word in ["agent", "tool", "mcp", "sdk", "api"]):
        return "智能体与开发者平台"
    if any(word in blob for word in ["video", "pose", "multimodal", "vision"]):
        return "多模态理解"
    if any(word in blob for word in ["embedding", "retrieval", "rag", "search", "memory"]):
        return "检索增强与向量模型"
    if any(word in blob for word in ["cuda", "gpu", "inference", "latency", "throughput", "vllm"]):
        return "推理性能与基础设施"
    if any(word in blob for word in ["safety", "security", "attack", "risk"]):
        return "安全与可信评测"
    if candidate.item_type == "paper" or "arxiv" in candidate.source.lower():
        return "机器学习研究"
    return "开发者生态与数据工具"


def chinese_summary(candidate: Candidate) -> str:
    source = readable_source(candidate.source)
    topic = topic_label(candidate)
    if candidate.item_type == "github_release":
        repo = candidate.raw.get("repo") or candidate.source.split(":", 1)[-1].strip()
        return f"{repo} 发布了新版本，建议优先查看新功能、兼容性变化、迁移说明、性能变化和依赖升级。"
    if candidate.item_type == "paper" or "arxiv" in candidate.source.lower():
        return f"这是一篇来自 {source} 的新论文，主题偏向“{topic}”。建议先看摘要、方法、实验设置、数据集和局限，再决定是否深入阅读全文。"
    return f"{source} 发布了新的科技内容，主题偏向“{topic}”。建议通过原文确认功能入口、可用范围、价格或接口变化。"


def comparison_note(candidate: Candidate) -> str:
    blob = f"{candidate.title} {candidate.summary}".lower()
    if any(word in blob for word in ["benchmark", "sota", "latency", "throughput", "pricing", "price", "cost"]):
        return "原文可能包含评测、价格或性能线索，建议直接核对原始指标和测试条件。"
    return "当前来源没有稳定可比的公开指标时，本快报不硬编性能对比。"
