from __future__ import annotations

from .models import Candidate


TRUSTED_SOURCE_MARKERS = [
    "OpenAI",
    "Anthropic",
    "Google",
    "DeepMind",
    "Meta",
    "Microsoft",
    "NVIDIA",
    "PyTorch",
    "TensorFlow",
    "Hugging Face",
    "GitHub Release",
    "arXiv",
]


def score_candidates(candidates: list[Candidate], config: dict) -> list[Candidate]:
    strong = [k.lower() for k in config.get("keywords", {}).get("strong", [])]
    weak = [k.lower() for k in config.get("keywords", {}).get("weak", [])]

    for candidate in candidates:
        blob = f"{candidate.title} {candidate.summary} {candidate.source}".lower()
        score = 0
        reasons: list[str] = []

        if any(marker.lower() in candidate.source.lower() for marker in TRUSTED_SOURCE_MARKERS):
            score += 3
            reasons.append("高可信来源")
        elif candidate.item_type in {"official", "github_release", "paper"}:
            score += 2
            reasons.append("结构化来源")

        strong_hits = [word for word in strong if word in blob]
        weak_hits = [word for word in weak if word in blob]
        if strong_hits:
            score += min(3, 1 + len(strong_hits) // 2)
            reasons.append("命中强信号关键词: " + ", ".join(strong_hits[:5]))
        if weak_hits:
            score += min(2, len(weak_hits))
            reasons.append("命中弱信号关键词: " + ", ".join(weak_hits[:5]))

        if candidate.item_type == "github_release":
            score += 1
            reasons.append("官方 release")
        if candidate.item_type == "paper":
            score += 1
            reasons.append("最新论文")
        if any(word in blob for word in ["benchmark", "sota", "latency", "throughput", "cost", "pricing"]):
            score += 1
            reasons.append("含可比较性能/成本线索")

        candidate.score = min(score, 10)
        candidate.reasons = reasons

    return sorted(candidates, key=lambda item: (item.score, item.published_at), reverse=True)

