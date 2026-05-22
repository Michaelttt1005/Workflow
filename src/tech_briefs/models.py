from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import re


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
        return "论文预印本"
    if source.startswith("GitHub Release:"):
        return "代码仓库发布"
    value = source.replace("Google Developers Blog", "Google 开发者博客")
    value = value.replace("OpenAI News", "OpenAI 官方新闻")
    value = value.replace("Anthropic News", "Anthropic 官方新闻")
    value = value.replace("Google DeepMind Blog", "Google DeepMind 博客")
    value = value.replace("Meta AI Blog", "Meta 人工智能博客")
    value = value.replace("Microsoft Research Blog", "微软研究博客")
    value = value.replace("NVIDIA Developer Blog", "NVIDIA 开发者博客")
    value = value.replace("PyTorch Blog", "深度学习框架博客")
    value = value.replace("TensorFlow Blog", "机器学习框架博客")
    value = value.replace("Hugging Face Blog", "模型社区博客")
    return value


def chinese_title(candidate: Candidate) -> str:
    raw = candidate.title.strip()
    lower = f"{raw} {candidate.source}".lower()
    if "arxiv" in candidate.source.lower():
        if any(word in lower for word in ["safety", "secure", "attack", "risk"]):
            return "智能体安全评测新论文"
        if any(word in lower for word in ["video", "multimodal", "vision", "pose"]):
            return "多模态与视频理解新论文"
        if any(word in lower for word in ["agent", "sandbox", "checkpoint", "rollback"]):
            return "智能体基础设施新论文"
        if any(word in lower for word in ["retrieval", "rag", "embedding", "memory"]):
            return "检索增强与向量模型新论文"
        if any(word in lower for word in ["training", "consistency", "reasoning"]):
            return "模型训练与推理能力新论文"
        return "机器学习研究新论文"
    if "github release" in candidate.source.lower():
        return _repo_chinese_title(candidate.raw.get("repo") or candidate.source)
    if "google" in candidate.source.lower():
        if "embedding" in lower:
            return "Google 发布多模态嵌入更新"
        if "litert" in lower or "on-device" in lower:
            return "Google 更新端侧生成式人工智能工具"
        return "Google 开发者生态更新"
    if "openai" in candidate.source.lower():
        return "OpenAI 官方更新"
    if "anthropic" in candidate.source.lower():
        return "Anthropic 官方更新"
    if "nvidia" in candidate.source.lower():
        return "NVIDIA 开发者生态更新"
    return _strip_marketing_english(raw) or "科技生态更新"


def chinese_topic_title(title: str) -> str:
    lower = title.lower()
    if any(word in lower for word in ["agent", "sandbox", "checkpoint", "rollback"]):
        return "智能体与执行环境"
    if any(word in lower for word in ["video", "pose", "multimodal", "vision"]):
        return "多模态理解"
    if any(word in lower for word in ["embedding", "retrieval", "rag", "memory"]):
        return "检索与知识库"
    if any(word in lower for word in ["safety", "security", "attack", "risk"]):
        return "安全与可信评测"
    if any(word in lower for word in ["on-device", "litert", "inference", "latency"]):
        return "端侧部署与推理性能"
    return "研究与工程进展"


def chinese_summary(candidate: Candidate) -> str:
    source = readable_source(candidate.source)
    lower = f"{candidate.title} {candidate.summary}".lower()
    if "arxiv" in candidate.source.lower():
        topic = chinese_topic_title(candidate.title)
        return f"{source} 收录的一篇关于“{topic}”的新论文，适合先阅读摘要与实验设置，再判断是否需要深入全文。"
    if candidate.item_type == "github_release":
        return "相关开源项目发布了新版本，建议重点查看发布说明中的破坏性变更、性能优化、依赖升级和迁移说明。"
    if "benchmark" in lower or "sota" in lower:
        return f"{source} 的更新包含可比较的性能或评测线索，适合优先核对原始数据和测试条件。"
    if "api" in lower:
        return f"{source} 的更新涉及开发者接口或平台能力，适合检查是否影响现有集成、调用成本或产品路线。"
    return f"{source} 发布了新的技术内容，适合通过原始链接确认功能、适用场景和限制。"


def _strip_marketing_english(title: str) -> str:
    if not title:
        return ""
    if re.fullmatch(r"[\x00-\x7f]+", title):
        return ""
    return title


def _repo_chinese_title(repo: str) -> str:
    lower = repo.lower()
    if "pytorch" in lower:
        return "深度学习框架发布新版本"
    if "tensorflow" in lower:
        return "机器学习框架发布新版本"
    if "jax" in lower:
        return "加速数值计算框架发布新版本"
    if "transformers" in lower or "diffusers" in lower:
        return "模型工具库发布新版本"
    if "vllm" in lower or "llama.cpp" in lower:
        return "模型推理框架发布新版本"
    if "langchain" in lower or "llama_index" in lower:
        return "智能体开发框架发布新版本"
    if "mlflow" in lower:
        return "机器学习实验管理工具发布新版本"
    if "ray" in lower:
        return "分布式计算框架发布新版本"
    if "arrow" in lower:
        return "数据处理基础库发布新版本"
    if "pandas" in lower:
        return "数据分析库发布新版本"
    if "numpy" in lower:
        return "科学计算库发布新版本"
    if "scikit-learn" in lower:
        return "机器学习库发布新版本"
    return "开源项目发布新版本"
