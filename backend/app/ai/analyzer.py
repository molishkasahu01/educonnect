import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from app.ai.llm_provider import OptionalLLMProvider
from app.data_sources.base import build_normalized_professional_document, normalize_whitespace


# All 19 school ecosystem indicators required by Part 9
SCHOOL_ECOSYSTEM_TAXONOMY: dict[str, tuple[str, list[str]]] = {
    "school_ownership": ("School Ownership", ["school owner", "school founder", "co-founder of school", "promoter", "proprietor", "founded", "k-12 school chain founder"]),
    "school_leadership": ("School Leadership", ["school leader", "head of school", "headmaster", "headmistress", "dean", "vice principal", "school leadership"]),
    "principal_experience": ("Principal Experience", ["principal", "former principal", "executive principal", "campus principal"]),
    "school_directorship": ("School Directorship", ["school director", "director of schools", "managing director", "academic director", "campus director"]),
    "trusteeship": ("Trusteeship", ["trustee", "board of trustees", "managing trustee", "school trust", "governing body", "board member"]),
    "education_consultancy": ("Education Consultancy", ["education consultant", "school consultant", "k-12 consultant", "academic consultant", "consultancy", "consulting"]),
    "education_advisory": ("Education Advisory", ["education advisor", "advisory board", "strategic advisor", "school advisor", "advisor to", "advisory"]),
    "education_entrepreneurship": ("Education Entrepreneurship", ["edupreneur", "education entrepreneur", "founder", "co-founder", "startup", "venture", "built a school"]),
    "school_group_management": ("School Group Management", ["school group", "school chain", "multi-campus", "group of schools", "chain of schools", "network of schools"]),
    "multi_school_relationships": ("Multi-School Relationships", ["multi-school", "across schools", "partner schools", "network of principals", "10+ schools", "20+ schools", "50+ schools", "cluster of schools", "school founders"]),
    "school_operations": ("School Operations", ["school operations", "campus operations", "admissions", "school setup", "greenfield school", "turnaround", "school management"]),
    "k12_education": ("K-12 Education", ["k-12", "k12", "cbse", "icse", "ib ", "igcse", "cambridge", "montessori", "primary school", "secondary school", "high school"]),
    "education_technology": ("Education Technology", ["edtech", "education technology", "lms", "digital classroom", "learning platform", "stem lab", "ai in education"]),
    "academic_leadership": ("Academic Leadership", ["curriculum", "pedagogy", "academic head", "chief academic", "instructional leadership", "NEP 2020", "nep"]),
    "teacher_development": ("Teacher Development", ["teacher training", "faculty development", "professional development", "educator coaching", "capacity building"]),
    "education_policy": ("Education Policy", ["education policy", "nep", "regulatory", "ministry", "education board", "compliance", "affiliation"]),
    "school_accreditation": ("School Accreditation", ["accreditation", "cbse affiliation", "ib authorization", "cis", "naac", "quality assurance", "inspection"]),
    "education_partnerships": ("Education Partnerships", ["partnerships", "b2b schools", "school partnerships", "institutional sales", "alliances", "mou"]),
    "school_network_development": ("School Network Development", ["school network", "franchise", "school expansion", "new campuses", "cluster expansion"]),
}

INFLUENCE_PATTERNS: dict[str, list[str]] = {
    "public_speaking": ["keynote", "speaker", "panelist", "tedx", "summit", "conference", "webinar host"],
    "professional_associations": ["association", "federation", "council", "chapter chair", "fellow", "committee", "rotary", "ficci", "cii", "nisa"],
    "advisory_experience": ["advisor", "advisory", "mentor", "board member", "counselor"],
    "leadership_experience": ["chief", "director", "principal", "founder", "vp", "head", "president", "chairperson"],
    "industry_participation": ["jury", "award", "summit", "roundtable", "forum", "symposium", "author", "published"],
}


@dataclass
class ExtractedAttribute:
    category: str
    attribute_name: str
    attribute_value: str
    evidence_text: str
    source_reference: str
    classification_type: str
    confidence: float


def _find_evidence_snippet(text: str, keywords: list[str]) -> Optional[str]:
    lower = text.lower()
    for kw in keywords:
        idx = lower.find(kw.lower())
        if idx != -1:
            start = max(0, idx - 60)
            end = min(len(text), idx + len(kw) + 80)
            snippet = text[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text):
                snippet = snippet + "..."
            return snippet
    return None


def extract_experience_years_from_text(text: str) -> tuple[Optional[float], Optional[str]]:
    if not text:
        return None, None
    # Explicit "X+ years" / "X years"
    m = re.search(
        r"(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s+(?:(?:of|across|in)\s+)?(?:[a-z0-9\-]+\s+){0,2}(?:experience|leadership|tenure|education|k-?12)",
        text,
        re.I,
    )
    if m:
        return float(m.group(1)), m.group(0)
    m2 = re.search(r"over\s+(\d{1,2})\s+(?:years?|yrs?)", text, re.I)
    if m2:
        return float(m2.group(1)), m2.group(0)
    # Date ranges like 2008-2024 or 2010–present
    years = [int(y) for y in re.findall(r"\b(19[7-9]\d|20[0-2]\d)\b", text)]
    if len(years) >= 2:
        span = max(years) - min(years)
        if 1 <= span <= 50:
            return float(span), f"Date span {min(years)}-{max(years)}"
    if "present" in text.lower() and years:
        current_year = datetime.now(timezone.utc).year
        span = current_year - min(years)
        if 1 <= span <= 50:
            return float(span), f"Date span {min(years)}-present"
    return None, None


def infer_seniority(role: str, exp_years: Optional[float], bio: str) -> tuple[str, str, str]:
    combined = f"{role} {bio}".lower()
    if any(k in combined for k in ["founder", "co-founder", "ceo", "managing director", "chairperson", "trustee", "owner", "president"]):
        return "Executive / Founder / Trustee", "OBSERVED_FACT" if role else "AI_DERIVED_CLASSIFICATION", "Matched executive/founder title"
    if any(k in combined for k in ["principal", "director", "head of school", "vp", "vice president", "senior consultant", "partner"]):
        return "Senior Education Leader", "AI_DERIVED_CLASSIFICATION", "Matched senior school leadership / director role"
    if exp_years is not None and exp_years >= 10:
        return "Senior Professional (10+ yrs)", "AI_DERIVED_CLASSIFICATION", f"Derived from {exp_years:.0f} documented years"
    if role or bio:
        return "Mid-Level / Specialist", "AI_DERIVED_CLASSIFICATION", "Derived from available role/bio text"
    return "Insufficient Data", "MISSING_INFORMATION", "No role or career duration provided"


def extract_organizations_from_text(text: str, current_org: Optional[str] = None) -> list[str]:
    orgs: list[str] = []
    if current_org:
        orgs.append(normalize_whitespace(current_org))
    patterns = [
        r"(?:at|with|founded|led|advisor to|director at|principal at)\s+([A-Z][A-Za-z0-9&\-\s]{2,50}?(?:School|Schools|Academy|Education|Foundation|Trust|Institute|Group|Learning|Consultancy|EdTech|Ventures|Network|International))",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text):
            candidate = normalize_whitespace(m.group(1))
            if candidate and candidate not in orgs:
                orgs.append(candidate)
    return orgs[:15]


class AIProfileAnalyzer:
    """Structured attribute extraction engine with strict evidence & provenance tracking."""

    def __init__(self):
        self.llm_provider = OptionalLLMProvider()

    def analyze_reference_profile(
        self,
        full_name: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        current_designation: Optional[str] = None,
        current_organization: Optional[str] = None,
        location: Optional[str] = None,
        professional_bio: Optional[str] = None,
        career_history: Optional[str] = None,
        education_sector_experience: Optional[str] = None,
        skills: Optional[list[str]] = None,
        additional_notes: Optional[str] = None,
    ) -> dict[str, Any]:
        now_iso = datetime.now(timezone.utc).isoformat()
        skills = skills or []

        text_fields = {
            "current_designation": current_designation or "",
            "current_organization": current_organization or "",
            "professional_bio": professional_bio or "",
            "career_history": career_history or "",
            "education_sector_experience": education_sector_experience or "",
            "additional_notes": additional_notes or "",
        }
        non_empty_substantive = [
            k for k, v in text_fields.items() if normalize_whitespace(v)
        ]

        missing_critical: list[str] = []
        if not normalize_whitespace(full_name):
            missing_critical.append("full_name")
        if not normalize_whitespace(current_designation):
            missing_critical.append("current_designation")
        if not normalize_whitespace(professional_bio) and not normalize_whitespace(career_history) and not normalize_whitespace(education_sector_experience):
            missing_critical.append("professional_bio_or_career_history")

        compliance_notice: Optional[str] = None
        if linkedin_url and len(non_empty_substantive) == 0:
            compliance_notice = (
                "Only a LinkedIn URL was provided. Authorized LinkedIn enrichment is not configured, "
                "and automated scraping or bypassing LinkedIn access controls is strictly prohibited. "
                "Please supply the professional's role, biography, career history, or an authorized export."
            )
            return {
                "analysis_status": "NEEDS_MORE_INFO",
                "compliance_notice": compliance_notice,
                "missing_critical_fields": missing_critical,
                "attributes": [
                    {
                        "category": "identity",
                        "attribute_name": "linkedin_reference_identifier",
                        "attribute_value": linkedin_url,
                        "evidence_text": linkedin_url,
                        "source_reference": "reference_form:linkedin_url",
                        "classification_type": "OBSERVED_FACT",
                        "confidence": 1.0,
                        "extraction_timestamp": now_iso,
                    },
                    {
                        "category": "identity",
                        "attribute_name": "profile_substance",
                        "attribute_value": "Missing structured profile details",
                        "evidence_text": "No bio, career history, or designation provided",
                        "source_reference": "validation:missing_fields",
                        "classification_type": "MISSING_INFORMATION",
                        "confidence": 1.0,
                        "extraction_timestamp": now_iso,
                    },
                ],
                "school_indicators": [],
                "influence_indicators": [],
                "organizations": [],
                "experience_years": None,
                "seniority": "Insufficient Data",
                "normalized_document": "",
                "analyzer_engine": self.llm_provider.active_provider_name(),
            }

        if linkedin_url:
            compliance_notice = (
                "LinkedIn URL recorded strictly as a user-provided reference identifier; "
                "all extracted attributes below are derived solely from user-supplied profile data."
            )

        attributes: list[dict[str, Any]] = []

        def add_attr(
            category: str,
            name: str,
            value: str,
            evidence: str,
            source_ref: str,
            cls_type: str,
            conf: float,
        ):
            attributes.append(
                {
                    "category": category,
                    "attribute_name": name,
                    "attribute_value": value,
                    "evidence_text": evidence,
                    "source_reference": source_ref,
                    "classification_type": cls_type,
                    "confidence": round(conf, 3),
                    "extraction_timestamp": now_iso,
                }
            )

        # 1. Observed Identity Facts
        if full_name:
            add_attr("identity", "full_name", full_name, full_name, "reference_form:full_name", "OBSERVED_FACT", 1.0)
        else:
            add_attr("identity", "full_name", "Not provided", "Missing full name", "reference_form:full_name", "MISSING_INFORMATION", 1.0)

        if current_designation:
            add_attr("identity", "current_position", current_designation, current_designation, "reference_form:current_designation", "OBSERVED_FACT", 1.0)
        else:
            add_attr("identity", "current_position", "Not provided", "Missing current designation", "reference_form:current_designation", "MISSING_INFORMATION", 1.0)

        if current_organization:
            add_attr("identity", "current_organization", current_organization, current_organization, "reference_form:current_organization", "OBSERVED_FACT", 1.0)

        if location:
            add_attr("identity", "location", location, location, "reference_form:location", "OBSERVED_FACT", 1.0)
        else:
            add_attr("identity", "location", "Not provided", "Location omitted", "reference_form:location", "MISSING_INFORMATION", 1.0)

        combined_text = "\n".join(
            f"[{k}] {v}" for k, v in text_fields.items() if normalize_whitespace(v)
        )
        if skills:
            combined_text += f"\n[skills] {', '.join(skills)}"

        exp_years, exp_evidence = extract_experience_years_from_text(combined_text)
        if exp_years is not None and exp_evidence:
            add_attr(
                "career_context",
                "experience_duration_years",
                f"{exp_years:.0f} years",
                exp_evidence,
                "reference_form:career_text",
                "OBSERVED_FACT",
                0.92,
            )
        else:
            add_attr(
                "career_context",
                "experience_duration_years",
                "Not documented with explicit dates/years",
                "No explicit year span or tenure duration detected",
                "reference_form:career_text",
                "MISSING_INFORMATION",
                1.0,
            )

        seniority, sen_cls, sen_ev = infer_seniority(current_designation or "", exp_years, combined_text)
        add_attr("identity", "professional_seniority", seniority, sen_ev, "ai_analyzer:seniority", sen_cls, 0.86 if sen_cls != "MISSING_INFORMATION" else 1.0)

        # 2. School Ecosystem Indicators
        detected_school_indicators: list[str] = []
        for ind_key, (ind_label, keywords) in SCHOOL_ECOSYSTEM_TAXONOMY.items():
            # Locate which field matched first for traceable source_reference
            matched_snippet = None
            matched_field = "combined_text"
            for field_name, field_val in text_fields.items():
                if not field_val:
                    continue
                snip = _find_evidence_snippet(field_val, keywords)
                if snip:
                    matched_snippet = snip
                    matched_field = field_name
                    break
            if not matched_snippet and skills:
                snip = _find_evidence_snippet(", ".join(skills), keywords)
                if snip:
                    matched_snippet = snip
                    matched_field = "skills"

            if matched_snippet:
                detected_school_indicators.append(ind_label)
                add_attr(
                    "school_ecosystem",
                    ind_key,
                    ind_label,
                    matched_snippet,
                    f"reference_form:{matched_field}",
                    "AI_DERIVED_CLASSIFICATION",
                    0.88,
                )

        # 3. Professional Influence Indicators
        detected_influence: list[str] = []
        for inf_key, keywords in INFLUENCE_PATTERNS.items():
            snip = _find_evidence_snippet(combined_text, keywords)
            if snip:
                label = inf_key.replace("_", " ").title()
                detected_influence.append(label)
                add_attr(
                    "influence",
                    inf_key,
                    label,
                    snip,
                    "reference_form:combined_text",
                    "AI_DERIVED_CLASSIFICATION",
                    0.84,
                )

        # 4. Organizations
        orgs = extract_organizations_from_text(combined_text, current_organization)
        for org in orgs:
            add_attr(
                "career_context",
                "documented_organization",
                org,
                org,
                "reference_form:organizations",
                "OBSERVED_FACT" if org == current_organization else "AI_DERIVED_CLASSIFICATION",
                0.95 if org == current_organization else 0.78,
            )

        # Optional LLM note if configured
        llm_enrichment = self.llm_provider.summarize_profile_context(combined_text)

        normalized_doc = build_normalized_professional_document(
            full_name=full_name,
            current_role=current_designation,
            organization=current_organization,
            location=location,
            professional_bio=professional_bio,
            career_history=career_history,
            education_segments=[education_sector_experience] if education_sector_experience else [],
            school_indicators=detected_school_indicators,
            organizations=orgs,
            skills=skills,
            influence_indicators=detected_influence,
        )

        status = "ANALYZED" if not missing_critical or len(detected_school_indicators) > 0 else "NEEDS_MORE_INFO"
        return {
            "analysis_status": status,
            "compliance_notice": compliance_notice,
            "missing_critical_fields": missing_critical,
            "attributes": attributes,
            "school_indicators": detected_school_indicators,
            "influence_indicators": detected_influence,
            "organizations": orgs,
            "experience_years": exp_years,
            "seniority": seniority,
            "normalized_document": normalized_doc,
            "analyzer_engine": self.llm_provider.active_provider_name(),
            "llm_enrichment": llm_enrichment,
        }

    def analyze_candidate_attributes(
        self,
        full_name: str,
        current_role: Optional[str],
        organization_name: Optional[str],
        location: Optional[str],
        professional_bio: Optional[str],
        experience_years: Optional[float],
        education_segments: list[str],
        school_indicators: list[str],
        organizations_list: list[str],
        skills: list[str],
        influence_indicators: list[str],
        source_name: str,
        source_record_id: str,
        verification_status: str,
    ) -> list[dict[str, Any]]:
        """Extract provenance-labeled attributes for a candidate profile (Part 15)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        src_ref = f"{source_name}:{source_record_id}"
        is_unverified = verification_status == "unverified"
        base_obs_cls = "UNVERIFIED" if is_unverified else "DIRECTLY_OBSERVED"

        attrs: list[dict[str, Any]] = []
        if current_role:
            attrs.append({
                "category": "identity",
                "attribute_name": "current_role",
                "attribute_value": current_role,
                "evidence_text": current_role,
                "source_reference": src_ref,
                "classification_type": base_obs_cls,
                "confidence": 0.95 if not is_unverified else 0.65,
                "extraction_timestamp": now_iso,
            })
        if organization_name:
            attrs.append({
                "category": "identity",
                "attribute_name": "organization",
                "attribute_value": organization_name,
                "evidence_text": organization_name,
                "source_reference": src_ref,
                "classification_type": base_obs_cls,
                "confidence": 0.95 if not is_unverified else 0.65,
                "extraction_timestamp": now_iso,
            })
        if experience_years is not None:
            attrs.append({
                "category": "career_context",
                "attribute_name": "experience_years",
                "attribute_value": f"{experience_years:.1f} years",
                "evidence_text": f"Source record reports {experience_years:.1f} years",
                "source_reference": src_ref,
                "classification_type": "SOURCE_SUPPORTED" if verification_status == "verified" else "UNVERIFIED",
                "confidence": 0.90 if verification_status == "verified" else 0.65,
                "extraction_timestamp": now_iso,
            })

        for ind in school_indicators:
            attrs.append({
                "category": "school_ecosystem",
                "attribute_name": ind.lower().replace(" ", "_"),
                "attribute_value": ind,
                "evidence_text": f"Documented indicator '{ind}' in source record",
                "source_reference": src_ref,
                "classification_type": "SOURCE_SUPPORTED",
                "confidence": 0.90,
                "extraction_timestamp": now_iso,
            })

        # Also run AI derivation on biography to surface additional documented indicators not explicitly tagged
        bio = professional_bio or ""
        existing_lower = {i.lower() for i in school_indicators}
        for ind_key, (ind_label, keywords) in SCHOOL_ECOSYSTEM_TAXONOMY.items():
            if ind_label.lower() in existing_lower:
                continue
            snip = _find_evidence_snippet(f"{current_role or ''} {bio}", keywords)
            if snip:
                attrs.append({
                    "category": "school_ecosystem",
                    "attribute_name": ind_key,
                    "attribute_value": ind_label,
                    "evidence_text": snip,
                    "source_reference": f"{src_ref}#ai_bio_extraction",
                    "classification_type": "AI_DERIVED",
                    "confidence": 0.80,
                    "extraction_timestamp": now_iso,
                })

        for inf in influence_indicators:
            attrs.append({
                "category": "influence",
                "attribute_name": inf.lower().replace(" ", "_"),
                "attribute_value": inf,
                "evidence_text": inf,
                "source_reference": src_ref,
                "classification_type": "SOURCE_SUPPORTED",
                "confidence": 0.85,
                "extraction_timestamp": now_iso,
            })

        return attrs
