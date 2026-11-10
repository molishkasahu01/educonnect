from typing import Any
from app.ranking.engine import RankingComputation


def build_candidate_explanation(
    candidate: dict[str, Any],
    computation: RankingComputation,
) -> dict[str, Any]:
    """Generate a distinct, evidence-linked explanation grounded strictly in observed candidate attributes."""
    reasons: list[str] = []
    evidence_links: list[dict[str, Any]] = []

    role_title = (candidate.get("current_role") or "").strip()
    org_name = (candidate.get("organization_name") or "").strip()
    location = (candidate.get("location") or "").strip()
    ver_status = (candidate.get("verification_status") or "unverified").lower()

    school_matches = [m for m in computation.matched_attributes if m["dimension"] == "school_ecosystem"]
    if school_matches:
        labels = [m["attribute"] for m in school_matches[:3]]
        reasons.append(f"documented {', '.join(labels)}")
    elif computation.school_ecosystem_relevance >= 40:
        reasons.append("K-12 education sector alignment")

    role_matches = [m for m in computation.matched_attributes if m["dimension"] == "professional_role"]
    if role_matches:
        role_desc = role_title if role_title else role_matches[0]["attribute"]
        if org_name:
            reasons.append(f"leadership role alignment as {role_desc} at {org_name}")
        else:
            reasons.append(f"comparable leadership role ({role_desc})")

    org_matches = [m for m in computation.matched_attributes if m["dimension"] == "organization_network"]
    if org_matches and computation.organization_network_overlap >= 30:
        reasons.append(f"school-network/entity signals ({org_matches[0]['attribute']})")

    if computation.semantic_similarity >= 68:
        reasons.append(f"strong semantic context alignment ({computation.semantic_similarity:.1f}/100)")

    inf_matches = [m for m in computation.matched_attributes if m["dimension"] == "influence"]
    if inf_matches:
        reasons.append(f"recorded influence indicators ({inf_matches[0]['attribute']})")

    exp_matches = [m for m in computation.matched_attributes if m["dimension"] == "experience"]
    if exp_matches:
        reasons.append(f"tenure depth ({exp_matches[0]['attribute']})")

    context_suffix = f" ({location})" if location else ""
    if not reasons:
        if computation.relevance_tier == "LOW_RELEVANCE":
            summary = (
                f"Low alignment with the reference profile (score {computation.relevance_score:.1f}/100): "
                f"available records show limited school ecosystem or leadership overlap."
            )
        else:
            summary = (
                f"Partial alignment with the reference profile (score {computation.relevance_score:.1f}/100) "
                f"based on semantic professional context similarity ({computation.semantic_similarity:.1f}/100)."
            )
    else:
        lead_prefix = (
            f"{role_title or 'Candidate'}{context_suffix} aligns with the reference profile via "
            if (role_title and not role_matches)
            else f"Matches the reference profile{context_suffix} because source records show "
        )
        joined = ", ".join(reasons[:-1]) + f", and {reasons[-1]}" if len(reasons) > 1 else reasons[0]
        summary = f"{lead_prefix}{joined}."

    if ver_status == "unverified":
        summary += " Provenance is unverified user/directory data and requires manual confirmation."

    if not computation.meets_minimum_evidence:
        summary += " Evidence confidence is capped due to sparse profile fields."

    src_name = candidate.get("primary_source") or "source"
    src_id = candidate.get("source_record_id") or str(candidate.get("id", ""))
    evidence_links.append({
        "source_name": src_name,
        "source_record_id": src_id,
        "source_url": candidate.get("source_url"),
        "verification_status": candidate.get("verification_status", "unverified"),
    })
    for m in computation.matched_attributes[:6]:
        evidence_links.append({
            "dimension": m["dimension"],
            "attribute": m["attribute"],
            "evidence": m["evidence"],
            "source_ref": m["source_ref"],
        })

    return {
        "summary_explanation": summary,
        "matched_attributes": computation.matched_attributes,
        "missing_evidence_notes": computation.missing_evidence_notes,
        "evidence_links": evidence_links,
        "generated_by": "deterministic_evidence_engine",
    }
