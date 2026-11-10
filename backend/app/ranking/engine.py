from dataclasses import dataclass
from typing import Any, Optional
from app.ai.analyzer import SCHOOL_ECOSYSTEM_TAXONOMY


DEFAULT_RANKING_WEIGHTS: dict[str, float] = {
    "semantic_similarity": 0.30,
    "school_ecosystem_relevance": 0.25,
    "professional_role_similarity": 0.15,
    "experience_similarity": 0.10,
    "organization_network_overlap": 0.10,
    "influence_indicators_score": 0.10,
}

ROLE_CLUSTERS: dict[str, set[str]] = {
    "school_leadership": {"principal", "head", "headmaster", "headmistress", "dean", "vice principal", "provost"},
    "governance_ownership": {"founder", "co-founder", "owner", "promoter", "trustee", "chairperson", "managing trustee", "proprietor"},
    "director_executive": {"director", "managing director", "ceo", "chief academic", "president", "executive", "superintendent"},
    "advisory_consultancy": {"consultant", "advisor", "advisory", "strategist", "specialist", "partner"},
    "edtech_partnerships": {"edtech", "partnership", "alliances", "growth", "curriculum", "academic head", "vp"},
}


@dataclass
class RankingComputation:
    relevance_score: float
    evidence_confidence: float
    meets_minimum_evidence: bool
    relevance_tier: str
    semantic_similarity: float
    school_ecosystem_relevance: float
    professional_role_similarity: float
    experience_similarity: float
    organization_network_overlap: float
    influence_indicators_score: float
    cross_encoder_score: Optional[float]
    available_components: dict[str, bool]
    weights_used: dict[str, float]
    missing_evidence_notes: list[str]
    matched_attributes: list[dict[str, Any]]


def _tokenize(text: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in (text or ""))
    return {t for t in cleaned.split() if len(t) > 2}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _extract_role_clusters(role_text: Optional[str]) -> set[str]:
    lower = (role_text or "").lower()
    matched = set()
    for cluster, keywords in ROLE_CLUSTERS.items():
        if any(kw in lower for kw in keywords):
            matched.add(cluster)
    return matched


def _infer_indicator_set(
    school_indicators: list[str],
    education_segments: list[str],
    bio: Optional[str],
    role: Optional[str],
    orgs: Optional[list[str]] = None,
) -> set[str]:
    result = {i.strip().lower() for i in school_indicators if i.strip()}
    for seg in education_segments:
        s_low = seg.strip().lower()
        if s_low:
            result.add(s_low)
    org_text = " ".join(orgs or [])
    combined = f"{role or ''} {org_text} {bio or ''}".lower()
    for _, (label, kws) in SCHOOL_ECOSYSTEM_TAXONOMY.items():
        if any(kw in combined for kw in kws):
            result.add(label.lower())
    if any(tok in combined for tok in ("school", "schools", "vidya", "principals", "k-12", "k12", "educare", "gurukul", "academics")):
        result.add("k-12 education")
    return result


class HybridRankingEngine:
    """Explainable, missing-evidence-aware hybrid ranking engine (Part 13)."""

    def __init__(self, weights: Optional[dict[str, float]] = None, model_version: str = "hybrid-v1.0"):
        self.weights = dict(weights or DEFAULT_RANKING_WEIGHTS)
        self.model_version = model_version

    def score_candidate(
        self,
        reference: dict[str, Any],
        candidate: dict[str, Any],
        semantic_score_100: float,
        cross_encoder_score: Optional[float] = None,
    ) -> RankingComputation:
        missing_notes: list[str] = []
        matched_attributes: list[dict[str, Any]] = []

        cand_role = candidate.get("current_role") or ""
        cand_org = candidate.get("organization_name") or ""
        cand_bio = candidate.get("professional_bio") or ""
        cand_exp = candidate.get("experience_years")
        cand_edu_segs = candidate.get("education_segments") or []
        cand_school_inds = candidate.get("school_indicators") or []
        cand_orgs = candidate.get("organizations_list") or ([cand_org] if cand_org else [])
        cand_skills = candidate.get("skills") or []
        cand_influence = candidate.get("influence_indicators") or []

        ref_role = reference.get("current_designation") or ""
        ref_bio = reference.get("professional_bio") or ""
        ref_exp = reference.get("experience_years")
        ref_school_inds = {x.lower() for x in (reference.get("school_indicators") or [])}
        ref_orgs = {x.lower() for x in (reference.get("organizations") or [])}
        ref_influence = {x.lower() for x in (reference.get("influence_indicators") or [])}
        ref_skills = {x.lower() for x in (reference.get("skills") or [])}

        # 1. Semantic similarity availability (include organization context for structured directory entries)
        has_semantic_doc = len(f"{cand_role} {cand_org} {cand_bio} {' '.join(cand_school_inds)}".strip()) >= 25
        if not has_semantic_doc:
            missing_notes.append("Candidate lacks sufficient descriptive biography/role text for reliable semantic embedding.")
        sem_score = round(max(0.0, min(100.0, semantic_score_100)), 2)

        # 2. School ecosystem relevance
        cand_ind_set = _infer_indicator_set(cand_school_inds, cand_edu_segs, cand_bio, cand_role, cand_orgs)
        has_school_context = bool(cand_school_inds or cand_edu_segs or cand_bio or cand_role or cand_orgs)
        if not has_school_context:
            school_score = 0.0
            missing_notes.append("No school ecosystem indicators or biography available.")
        else:
            ref_ind_norm = ref_school_inds or {"k-12 education", "school leadership", "education consultancy", "education advisory"}
            overlap_inds = ref_ind_norm & cand_ind_set
            # Calibrate against effective reference core breadth so concise public directory cards aren't diluted across 10+ optional taxonomy tags
            core_denom = max(1, min(len(ref_ind_norm), 4))
            ref_recall = min(1.0, len(overlap_inds) / core_denom)
            breadth_bonus = min(1.0, len(cand_ind_set) / 4.0) if overlap_inds else 0.0
            school_score = round(min(100.0, (0.72 * ref_recall + 0.28 * breadth_bonus) * 100.0), 2)
            for ind in sorted(overlap_inds)[:6]:
                matched_attributes.append({
                    "dimension": "school_ecosystem",
                    "attribute": ind.title(),
                    "evidence": f"Candidate documented '{ind.title()}' aligning with reference profile",
                    "source_ref": f"{candidate.get('primary_source', 'source')}:{candidate.get('source_record_id', '')}",
                })

        # 3. Professional role similarity
        has_role = bool(cand_role.strip())
        if not has_role:
            role_score = 0.0
            missing_notes.append("Candidate current role/designation is missing.")
        else:
            ref_clusters = _extract_role_clusters(f"{ref_role} {ref_bio}")
            cand_clusters = _extract_role_clusters(f"{cand_role} {cand_bio[:200]}")
            cluster_sim = _jaccard(ref_clusters, cand_clusters)
            # K-12 executive leadership clusters are mutually relevant discovery targets
            exec_clusters = {"school_leadership", "governance_ownership", "director_executive", "advisory_consultancy"}
            ref_exec = bool(ref_clusters & exec_clusters)
            cand_exec = bool(cand_clusters & exec_clusters)
            role_org_low = f"{cand_role} {cand_org}".lower()
            is_k12_ecosystem = (
                "k-12 education" in cand_ind_set
                or any(k in role_org_low for k in ("school", "k-12", "education", "vidya", "academy", "principals", "educare", "podar"))
            )
            exec_affinity = 0.80 if (ref_exec and cand_exec and is_k12_ecosystem) else 0.0
            effective_cluster_sim = max(cluster_sim, exec_affinity)
            token_sim = _jaccard(_tokenize(ref_role), _tokenize(cand_role))
            role_score = round(min(100.0, (0.72 * effective_cluster_sim + 0.28 * token_sim) * 100.0), 2)
            if effective_cluster_sim > 0 or token_sim > 0.2:
                matched_attributes.append({
                    "dimension": "professional_role",
                    "attribute": cand_role,
                    "evidence": f"Role cluster alignment ({', '.join(sorted((ref_clusters & cand_clusters) or (cand_clusters & exec_clusters))) or 'role terminology'})",
                    "source_ref": f"{candidate.get('primary_source', 'source')}:{candidate.get('source_record_id', '')}",
                })

        # 4. Experience similarity
        has_exp = cand_exp is not None and ref_exp is not None
        if not has_exp:
            exp_score = 0.0
            if cand_exp is None:
                missing_notes.append("Candidate years of experience not documented with explicit dates.")
        else:
            diff = abs(float(ref_exp) - float(cand_exp))
            base = max(0.0, 1.0 - diff / max(float(ref_exp), 15.0))
            senior_bonus = 0.15 if (float(cand_exp) >= 10 and float(ref_exp) >= 10) else 0.0
            exp_score = round(min(100.0, (base + senior_bonus) * 100.0), 2)
            if exp_score >= 60:
                matched_attributes.append({
                    "dimension": "experience",
                    "attribute": f"{float(cand_exp):.0f} years experience",
                    "evidence": f"Documented {float(cand_exp):.0f} years vs reference {float(ref_exp):.0f} years",
                    "source_ref": f"{candidate.get('primary_source', 'source')}:{candidate.get('source_record_id', '')}",
                })

        # 5. Organization and network overlap
        has_orgs = bool(cand_orgs or cand_org)
        if not has_orgs:
            org_score = 0.0
            missing_notes.append("Candidate organization affiliations are not documented.")
        else:
            def _norm_org_tokens(items: list[str] | set[str]) -> set[str]:
                toks: set[str] = set()
                for o in items:
                    for t in _tokenize(o):
                        toks.add("school" if t == "schools" else t)
                return toks

            cand_org_tokens = _norm_org_tokens(cand_orgs)
            ref_org_tokens = _norm_org_tokens(ref_orgs)
            exact_org_overlap = {o.lower() for o in cand_orgs} & ref_orgs
            edu_org_terms = {
                "school", "academy", "education", "eduventures", "foundation", "trust",
                "learning", "advisory", "consultancy", "network", "group", "chain",
                "cbse", "ib", "k12", "public", "international",
            }
            cand_edu_org = cand_org_tokens & edu_org_terms
            ref_edu_org = ref_org_tokens & edu_org_terms
            if cand_edu_org and ref_edu_org:
                # Both are school-ecosystem institutions -> base ecosystem class alignment + token Jaccard
                class_sim = max(0.75, _jaccard(cand_edu_org, ref_edu_org))
            elif cand_edu_org:
                class_sim = 0.55
            else:
                class_sim = 0.0
            token_overlap = _jaccard(cand_org_tokens, ref_org_tokens)
            skill_overlap = _jaccard({s.lower() for s in cand_skills}, ref_skills)
            org_score = round(
                min(100.0, ((0.30 if exact_org_overlap else 0.0) + 0.65 * class_sim + 0.20 * token_overlap + 0.15 * skill_overlap) * 100.0),
                2,
            )
            if exact_org_overlap or cand_edu_org:
                matched_attributes.append({
                    "dimension": "organization_network",
                    "attribute": ", ".join(cand_orgs[:3]),
                    "evidence": f"Institutional ecosystem alignment across {', '.join(cand_orgs[:3])}",
                    "source_ref": f"{candidate.get('primary_source', 'source')}:{candidate.get('source_record_id', '')}",
                })

        # 6. Influence indicators
        has_influence = bool(cand_influence or cand_bio)
        if not has_influence:
            inf_score = 0.0
            missing_notes.append("No influence indicators documented.")
        else:
            cand_inf_norm = {i.lower() for i in cand_influence}
            cand_inf_tokens = _tokenize(" ".join(cand_influence) + " " + cand_bio[:400])
            ref_inf_tokens = _tokenize(" ".join(ref_influence) + " " + ref_bio[:400])
            direct_inf_overlap = cand_inf_norm & ref_influence
            inf_signal_words = {
                "keynote", "speaker", "panelist", "board", "trustee", "advisor", "advisory",
                "founder", "network", "schools", "principals", "council", "association",
                "fellow", "author", "chair", "mentors", "accreditation", "campus", "campuses",
                "owners", "promoters", "committee", "forum", "summit",
            }
            cand_signals = cand_inf_tokens & inf_signal_words
            ref_signals = ref_inf_tokens & inf_signal_words
            # Combine reference-signal alignment and verified K-12 influence depth
            k12_inf_depth = min(1.0, len(cand_signals) / 4.0) if cand_influence and ("k-12 education" in cand_ind_set or "school" in (cand_role + cand_bio).lower()) else min(0.35, len(cand_signals) / 6.0)
            sig_overlap = len(cand_signals & ref_signals) / max(1, len(ref_signals)) if ref_signals else 0.0
            direct_ratio = len(direct_inf_overlap) / max(1, len(ref_influence)) if ref_influence else 0.0
            breadth = min(1.0, len(cand_influence) / 2.0)
            inf_score = round(min(100.0, (0.45 * k12_inf_depth + 0.25 * sig_overlap + 0.15 * direct_ratio + 0.15 * breadth) * 100.0), 2)
            if cand_influence:
                matched_attributes.append({
                    "dimension": "influence",
                    "attribute": ", ".join(cand_influence[:3]),
                    "evidence": f"Documented influence: {', '.join(cand_influence[:3])}",
                    "source_ref": f"{candidate.get('primary_source', 'source')}:{candidate.get('source_record_id', '')}",
                })

        available_components = {
            "semantic_similarity": has_semantic_doc,
            "school_ecosystem_relevance": has_school_context,
            "professional_role_similarity": has_role,
            "experience_similarity": has_exp,
            "organization_network_overlap": has_orgs,
            "influence_indicators_score": has_influence,
        }
        scores_map = {
            "semantic_similarity": sem_score,
            "school_ecosystem_relevance": school_score,
            "professional_role_similarity": role_score,
            "experience_similarity": exp_score,
            "organization_network_overlap": org_score,
            "influence_indicators_score": inf_score,
        }

        # Missing-evidence-aware normalization
        avail_weight_sum = sum(
            self.weights[k] for k, is_avail in available_components.items() if is_avail
        )
        if avail_weight_sum > 0:
            normalized_score = sum(
                self.weights[k] * scores_map[k]
                for k, is_avail in available_components.items()
                if is_avail
            ) / avail_weight_sum
        else:
            normalized_score = 0.0

        # Blend cross-encoder only if enabled and computed
        if cross_encoder_score is not None:
            normalized_score = 0.85 * normalized_score + 0.15 * cross_encoder_score

        # Minimum evidence requirement check (Part 13)
        populated_core = sum([
            bool(cand_role.strip()),
            bool(cand_bio.strip()),
            bool(cand_school_inds or cand_edu_segs),
            cand_exp is not None,
            bool(cand_orgs),
        ])
        avail_count = sum(1 for v in available_components.values() if v)
        meets_minimum_evidence = has_semantic_doc and populated_core >= 2 and avail_count >= 3

        if not meets_minimum_evidence:
            # Conservative guardrail so sparse profiles cannot artificially rank at top
            normalized_score = normalized_score * 0.65

        relevance_score = round(max(0.0, min(100.0, normalized_score)), 2)

        # Calibrated Independent Evidence Confidence (NEVER equal to relevance_score!)
        # Combines structural completeness, evidence richness/depth, matched attributes,
        # source verification tier, reported confidence, and data freshness.
        completeness_ratio = populated_core / 5.0
        bio_depth = min(1.0, len(cand_bio.strip()) / 260.0)
        ind_depth = min(1.0, (len(cand_school_inds) + len(cand_edu_segs)) / 4.0)
        skill_depth = min(1.0, len(cand_skills) / 5.0)
        inf_depth = min(1.0, len(cand_influence) / 3.0)
        org_depth = min(1.0, len(cand_orgs) / 3.0)
        richness_depth = (
            0.30 * bio_depth
            + 0.22 * ind_depth
            + 0.18 * skill_depth
            + 0.15 * inf_depth
            + 0.15 * org_depth
        )
        matched_density = min(1.0, len(matched_attributes) / 7.0)

        ver_status = (candidate.get("verification_status") or "unverified").lower()
        has_src_url = bool(candidate.get("source_url") or candidate.get("linkedin_url"))
        if ver_status == "verified" and has_src_url:
            source_trust = 1.0
        elif ver_status == "verified":
            source_trust = 0.90
        else:
            source_trust = 0.65 if has_src_url else 0.56

        data_conf = float(candidate.get("data_confidence") or 0.6)
        freshness_days = max(0, int(candidate.get("data_freshness_days") or 0))
        freshness_factor = max(0.40, 1.0 - (min(365, freshness_days) / 450.0))

        raw_confidence = (
            0.26 * completeness_ratio
            + 0.24 * richness_depth
            + 0.15 * matched_density
            + 0.15 * data_conf
            + 0.12 * source_trust
            + 0.08 * freshness_factor
        ) * 100.0
        if not meets_minimum_evidence:
            raw_confidence = min(raw_confidence, 42.0)
        evidence_confidence = round(max(5.0, min(99.0, raw_confidence)), 2)

        if relevance_score >= 62.0 and meets_minimum_evidence:
            tier = "HIGHLY_RELEVANT"
        elif relevance_score >= 42.0:
            tier = "PARTIALLY_RELEVANT"
        else:
            tier = "LOW_RELEVANCE"

        return RankingComputation(
            relevance_score=relevance_score,
            evidence_confidence=evidence_confidence,
            meets_minimum_evidence=meets_minimum_evidence,
            relevance_tier=tier,
            semantic_similarity=sem_score,
            school_ecosystem_relevance=school_score,
            professional_role_similarity=role_score,
            experience_similarity=exp_score,
            organization_network_overlap=org_score,
            influence_indicators_score=inf_score,
            cross_encoder_score=cross_encoder_score,
            available_components=available_components,
            weights_used=dict(self.weights),
            missing_evidence_notes=missing_notes,
            matched_attributes=matched_attributes,
        )
