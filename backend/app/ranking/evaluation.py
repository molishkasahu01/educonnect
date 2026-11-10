import math
from typing import Any


RELEVANCE_GRADE_MAP: dict[str, float] = {
    "RELEVANT": 2.0,
    "PARTIALLY_RELEVANT": 1.0,
    "IRRELEVANT": 0.0,
}

BINARY_RELEVANT_LABELS = {"RELEVANT"}


def precision_at_k(ranked_ids: list[str], label_map: dict[str, str], k: int) -> float:
    top = ranked_ids[:k]
    if not top:
        return 0.0
    hits = sum(1 for cid in top if label_map.get(cid) in BINARY_RELEVANT_LABELS)
    return round(hits / len(top), 4)


def recall_at_k(ranked_ids: list[str], label_map: dict[str, str], k: int) -> float:
    total_rel = sum(1 for lbl in label_map.values() if lbl in BINARY_RELEVANT_LABELS)
    if total_rel == 0:
        return 0.0
    top = ranked_ids[:k]
    hits = sum(1 for cid in top if label_map.get(cid) in BINARY_RELEVANT_LABELS)
    return round(hits / total_rel, 4)


def ndcg_at_k(ranked_ids: list[str], label_map: dict[str, str], k: int) -> float:
    top = ranked_ids[:k]
    if not top:
        return 0.0

    def dcg(ids: list[str]) -> float:
        total = 0.0
        for idx, cid in enumerate(ids, start=1):
            rel = RELEVANCE_GRADE_MAP.get(label_map.get(cid, "IRRELEVANT"), 0.0)
            total += (2.0 ** rel - 1.0) / math.log2(idx + 1)
        return total

    actual_dcg = dcg(top)
    ideal_sorted = sorted(
        label_map.keys(),
        key=lambda cid: RELEVANCE_GRADE_MAP.get(label_map[cid], 0.0),
        reverse=True,
    )[:k]
    ideal_dcg = dcg(ideal_sorted)
    if ideal_dcg <= 0:
        return 0.0
    return round(actual_dcg / ideal_dcg, 4)


def mean_reciprocal_rank(ranked_ids: list[str], label_map: dict[str, str]) -> float:
    for idx, cid in enumerate(ranked_ids, start=1):
        if label_map.get(cid) in BINARY_RELEVANT_LABELS:
            return round(1.0 / idx, 4)
    return 0.0


def evaluate_ranking_order(ranked_ids: list[str], label_map: dict[str, str]) -> dict[str, float]:
    return {
        "precision_at_10": precision_at_k(ranked_ids, label_map, 10),
        "precision_at_20": precision_at_k(ranked_ids, label_map, 20),
        "recall_at_20": recall_at_k(ranked_ids, label_map, 20),
        "ndcg_at_10": ndcg_at_k(ranked_ids, label_map, 10),
        "mrr": mean_reciprocal_rank(ranked_ids, label_map),
    }


def compute_keyword_baseline_scores(reference_text: str, candidates: list[dict[str, Any]]) -> list[tuple[str, float]]:
    ref_tokens = {
        t.lower()
        for t in "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in reference_text).split()
        if len(t) > 2
    }
    scored: list[tuple[str, float]] = []
    for cand in candidates:
        doc = " ".join([
            cand.get("current_role") or "",
            cand.get("professional_bio") or "",
            " ".join(cand.get("school_indicators") or []),
            " ".join(cand.get("skills") or []),
        ])
        cand_tokens = {
            t.lower()
            for t in "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in doc).split()
            if len(t) > 2
        }
        overlap = len(ref_tokens & cand_tokens)
        score = overlap / max(1, len(ref_tokens))
        scored.append((str(cand["source_record_id"]), round(score * 100.0, 2)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
