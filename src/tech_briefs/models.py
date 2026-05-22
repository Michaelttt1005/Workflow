from __future__ import annotations

import re
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
    title = display_title(candidate)
    date = candidate.published_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    excerpt = summary_excerpt(candidate, 420)
    if candidate.item_type == "github_release":
        repo = candidate.raw.get("repo") or candidate.source.split(":", 1)[-1].strip()
        tag = candidate.raw.get("tag") or title
        return f"{repo} 在 {date} 发布 {tag}。Release notes 摘要：{excerpt}"
    if candidate.item_type == "paper" or "arxiv" in candidate.source.lower():
        return f"《{title}》是 {source} 在 {date} 收录的论文。摘要要点：{excerpt}"
    return f"{source} 在 {date} 发布《{title}》。原文摘要：{excerpt}"


def purpose_note(candidate: Candidate) -> str:
    topic = topic_label(candidate)
    title = display_title(candidate)
    if candidate.item_type == "github_release":
        repo = candidate.raw.get("repo") or candidate.source.split(":", 1)[-1].strip()
        return f"判断 {repo} 这次版本发布是否会影响现有开发、训练、推理或数据工作流。"
    if candidate.item_type == "paper" or "arxiv" in candidate.source.lower():
        return f"判断《{title}》在“{topic}”方向的新方法、数据或评测是否值得继续跟进。"
    return f"判断这条来自 {readable_source(candidate.source)} 的发布是否带来新的产品能力、接口变化或工程实践。"


def feature_note(candidate: Candidate) -> str:
    sentences = summary_sentences(candidate.summary, 2)
    if sentences:
        return "原始摘要/发布说明中的具体线索：" + " / ".join(sentences)
    if candidate.reasons:
        return "筛选命中信号：" + "；".join(candidate.reasons[:3])
    return f"当前候选只提供标题和链接，标题为《{display_title(candidate)}》，需要打开原文核对完整细节。"


def comparison_note(candidate: Candidate) -> str:
    blob = f"{candidate.title} {candidate.summary}".lower()
    terms = ["benchmark", "sota", "latency", "throughput", "pricing", "price", "cost", "speed", "faster"]
    hits = [word for word in terms if word in blob]
    if hits:
        sentence = sentence_with_any(candidate.summary or candidate.title, hits) or summary_excerpt(candidate, 220)
        return f"原文出现 {', '.join(hits[:4])} 相关线索：{sentence}"
    return "暂无可信公开对比数据；标题和摘要中没有提供统一 benchmark、价格、延迟或吞吐指标。"


def audience_note(candidate: Candidate) -> str:
    topic = topic_label(candidate)
    if "推理" in topic or "基础设施" in topic:
        return "适合负责模型训练、推理服务、GPU 成本优化和平台稳定性的工程团队。"
    if "智能体" in topic:
        return "适合构建智能体、工具调用、开发者平台和自动化工作流的团队。"
    if "检索" in topic:
        return "适合做企业知识库、搜索、RAG、向量数据库和多语言检索的团队。"
    if "安全" in topic:
        return "适合安全、合规、模型评测和可信 AI 治理相关团队。"
    if candidate.item_type == "paper" or "arxiv" in candidate.source.lower():
        return "适合跟踪相关论文方向、准备复现实验或寻找新研究 idea 的读者。"
    return "适合需要评估新工具、新 API、新模型能力或开源生态变化的产品和工程团队。"


def summary_excerpt(candidate: Candidate, limit: int = 360) -> str:
    text = compact_text(candidate.summary)
    if not text:
        return f"原始来源没有提供摘要；可通过直达链接查看《{display_title(candidate)}》的完整内容。"
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def summary_sentences(text: str, max_count: int = 2) -> list[str]:
    cleaned = compact_text(text)
    if not cleaned:
        return []
    parts = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", cleaned) if part.strip()]
    if not parts:
        return [cleaned[:260]]
    return [part[:260] for part in parts[:max_count]]


def sentence_with_any(text: str, needles: list[str]) -> str:
    for sentence in summary_sentences(text, 8):
        lower = sentence.lower()
        if any(needle in lower for needle in needles):
            return sentence
    return ""


def compact_text(text: str) -> str:
    return " ".join((text or "").replace("\n", " ").split())


def is_major_alert_candidate(candidate: Candidate, min_score: int) -> bool:
    if candidate.score < min_score:
        return False
    if candidate.item_type in {"official", "github_release"}:
        return True
    return False
