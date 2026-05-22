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
        category = source.replace("arXiv", "", 1).strip()
        return f"arXiv {category} 论文" if category else "arXiv 论文"
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


def is_major_alert_candidate(candidate: Candidate, min_score: int) -> bool:
    if candidate.score < min_score:
        return False
    if candidate.item_type in {"official", "github_release"}:
        return True
    return False
