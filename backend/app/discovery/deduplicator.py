from typing import Optional
from app.ai.embeddings import embedding_service
from app.data_sources.base import normalize_org_name, normalize_person_name


def is_confident_duplicate(
    cand_a: dict,
    cand_b: dict,
    embedding_a: Optional[list[float]] = None,
    embedding_b: Optional[list[float]] = None,
) -> tuple[bool, float, str]:
    """
    Conservative candidate deduplication (Part 10 & Part 12).
    Never merges candidates automatically when identity confidence is insufficient.
    """
    # 1. Exact source + source_record_id
    if (
        cand_a.get("primary_source")
        and cand_a.get("primary_source") == cand_b.get("primary_source")
        and cand_a.get("source_record_id")
        and cand_a.get("source_record_id") == cand_b.get("source_record_id")
    ):
        return True, 1.0, "exact_source_record_id"

    # 2. Exact LinkedIn URL (only if both non-null)
    li_a = (cand_a.get("linkedin_url") or "").strip().lower().rstrip("/")
    li_b = (cand_b.get("linkedin_url") or "").strip().lower().rstrip("/")
    if li_a and li_b and li_a == li_b:
        return True, 0.99, "exact_linkedin_url"

    # 3. Normalized identity attributes (name + org / name + high semantic match)
    name_a = normalize_person_name(cand_a.get("full_name") or cand_a.get("name"))
    name_b = normalize_person_name(cand_b.get("full_name") or cand_b.get("name"))
    if not name_a or name_a != name_b:
        return False, 0.0, "distinct_names"

    org_a = normalize_org_name(cand_a.get("organization_name") or cand_a.get("organization"))
    org_b = normalize_org_name(cand_b.get("organization_name") or cand_b.get("organization"))
    loc_a = (cand_a.get("location") or "").strip().lower()
    loc_b = (cand_b.get("location") or "").strip().lower()

    if org_a and org_b:
        if org_a == org_b or org_a in org_b or org_b in org_a:
            return True, 0.95, "normalized_name_and_organization"
        stop = {"of", "the", "and", "for", "in", "at", "&"}
        toks_a = {t for t in org_a.split() if len(t) > 1 and t not in stop}
        toks_b = {t for t in org_b.split() if len(t) > 1 and t not in stop}
        shared_org = toks_a & toks_b
        if len(shared_org) >= 2 and (len(shared_org) / min(len(toks_a), len(toks_b))) >= 0.5:
            return True, 0.93, "normalized_name_and_shared_org_tokens"

    if embedding_a and embedding_b:
        cos = embedding_service.cosine_similarity(embedding_a, embedding_b)
        if cos >= 0.94 and (not loc_a or not loc_b or loc_a == loc_b):
            return True, round(cos, 3), "normalized_name_and_semantic_bio_match"

    # Insufficient identity confidence -> do not merge!
    return False, 0.45, "same_name_insufficient_identity_confidence"
