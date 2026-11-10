import json
import re
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import httpx
from app.schemas.candidate import NormalizedCandidateRecord


BLOCKED_SCRAPING_DOMAINS = ("linkedin.com", "lnkd.in")


def normalize_whitespace(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_person_name(name: Optional[str]) -> str:
    cleaned = normalize_whitespace(name).lower()
    cleaned = re.sub(r"^(?:dr\.?|prof\.?|mr\.?|ms\.?|mrs\.?|brigadier|brig\.?|capt\.?|major|general|shri|sri)\s+", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Collapse consecutive single-letter initials (e.g. "s k rathor" -> "sk rathor") for consistent dedup
    while True:
        collapsed = re.sub(r"\b([a-z])\s+([a-z])\b", r"\1\2", cleaned)
        if collapsed == cleaned:
            break
        cleaned = collapsed
    return cleaned


def normalize_org_name(name: Optional[str]) -> str:
    cleaned = normalize_whitespace(name).lower()
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s]", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_list_field(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [normalize_whitespace(str(x)) for x in raw if normalize_whitespace(str(x))]
    text = str(raw).strip()
    if not text:
        return []
    sep = ";" if ";" in text else ("|" if "|" in text else ",")
    return [normalize_whitespace(item) for item in text.split(sep) if normalize_whitespace(item)]


def is_restricted_social_url(url: Optional[str]) -> bool:
    if not url:
        return False
    lower = url.lower()
    return any(domain in lower for domain in BLOCKED_SCRAPING_DOMAINS)


def build_normalized_professional_document(
    full_name: Optional[str] = None,
    current_role: Optional[str] = None,
    organization: Optional[str] = None,
    location: Optional[str] = None,
    professional_bio: Optional[str] = None,
    career_history: Optional[str] = None,
    education_segments: Optional[list[str]] = None,
    school_indicators: Optional[list[str]] = None,
    organizations: Optional[list[str]] = None,
    skills: Optional[list[str]] = None,
    influence_indicators: Optional[list[str]] = None,
) -> str:
    """Construct a normalized professional context document for semantic embedding."""
    sections = []
    if current_role or organization:
        sections.append(f"Role: {current_role or ''} at {organization or ''}".strip())
    if location:
        sections.append(f"Location: {location}")
    if professional_bio:
        sections.append(f"Biography: {normalize_whitespace(professional_bio)}")
    if career_history:
        sections.append(f"Career History: {normalize_whitespace(career_history)}")
    if education_segments:
        sections.append(f"Education Experience: {', '.join(education_segments)}")
    if school_indicators:
        sections.append(f"School Ecosystem Indicators: {', '.join(school_indicators)}")
    if organizations:
        sections.append(f"Organizations: {', '.join(organizations)}")
    if skills:
        sections.append(f"Skills & Competencies: {', '.join(skills)}")
    if influence_indicators:
        sections.append(f"Professional Influence: {', '.join(influence_indicators)}")
    if not sections and full_name:
        sections.append(f"Profile: {full_name}")
    return "\n".join(sections)


def check_candidate_eligibility(record: NormalizedCandidateRecord) -> tuple[bool, Optional[str]]:
    if not record.name or len(record.name.strip()) < 2:
        return False, "Missing valid full name"
    if str(record.verification_status).lower() == "synthetic":
        return False, "Synthetic candidate records are prohibited on EduConnect"
    has_context = any([
        bool(record.current_role),
        bool(record.professional_bio),
        bool(record.school_indicators),
        bool(record.education_segments),
        bool(record.skills),
    ])
    if not has_context:
        return False, "Insufficient profile context for indexing"
    return True, None


class BaseDataSourceAdapter(ABC):
    adapter_type: str = "base"

    @abstractmethod
    def ingest(self, payload: Any, **kwargs) -> list[NormalizedCandidateRecord]:
        """Parse and normalize records into canonical NormalizedCandidateRecord items."""
        raise NotImplementedError

    @staticmethod
    def _deterministic_uuid(source: str, source_record_id: str) -> uuid.UUID:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"edxso:{source}:{source_record_id}")


def _is_allowed_by_robots(robots_text: str, path: str, bot_name: str = "edxso-research-bot") -> bool:
    """RFC-9309 longest-match evaluator for robots.txt Allow/Disallow rules."""
    target = path or "/"
    current_agents: list[str] = []
    seen_directive = False
    best_specific: list[tuple[int, bool]] = []
    best_wildcard: list[tuple[int, bool]] = []

    for raw_line in robots_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, val = [p.strip() for p in line.split(":", 1)]
        kl = key.lower()
        if kl == "user-agent":
            if seen_directive:
                current_agents = []
                seen_directive = False
            current_agents.append(val.lower())
        elif kl in ("allow", "disallow"):
            seen_directive = True
            if not val:
                continue
            prefix = val
            matches = target.startswith(prefix) or (prefix == "/" and target.startswith("/"))
            if not matches:
                continue
            rule = (len(prefix), kl == "allow")
            if any(a != "*" and a in bot_name for a in current_agents):
                best_specific.append(rule)
            elif "*" in current_agents:
                best_wildcard.append(rule)

    candidates = best_specific or best_wildcard
    if not candidates:
        return True
    # Longest path wins; on equal length, Allow takes precedence per RFC 9309
    best_len = max(c[0] for c in candidates)
    tied = [c for c in candidates if c[0] == best_len]
    return any(allowed for _, allowed in tied)


def clean_linkedin_profile_url(url: Optional[str]) -> Optional[str]:
    """Normalize a verified public LinkedIn /in/ profile URL without inventing links."""
    raw = normalize_whitespace(url)
    if not raw:
        return None
    m = re.match(r"^https?://(?:[a-z0-9-]+\.)?linkedin\.com(/in/[A-Za-z0-9_%\-]+/?)", raw, flags=re.I)
    if not m:
        return None
    slug_path = m.group(1)
    if not slug_path.endswith("/"):
        slug_path += "/"
    return f"https://www.linkedin.com{slug_path}"


def _safe_http_get_no_restricted_redirects(url: str, timeout_s: float = 10.0) -> httpx.Response:
    """Fetch a public URL following up to 3 safe same-policy redirects while blocking restricted social domains."""
    current_url = url
    headers = {"User-Agent": "EDXSO-Research-Bot/1.0"}
    with httpx.Client(timeout=timeout_s, follow_redirects=False) as client:
        for _ in range(4):
            if is_restricted_social_url(current_url):
                raise PermissionError("Restricted social domain is blocked by compliance policy.")
            resp = client.get(current_url, headers=headers)
            if resp.status_code in (301, 302, 303, 307, 308):
                location = resp.headers.get("location")
                if not location:
                    break
                next_url = urljoin(current_url, location)
                if is_restricted_social_url(next_url):
                    raise PermissionError("Redirect target belongs to a restricted social domain.")
                current_url = next_url
                continue
            return resp
    raise httpx.TooManyRedirects(f"Too many redirects fetching {url}")


def fetch_permitted_public_url(url: str, timeout_s: float = 10.0) -> list[dict[str, Any]]:
    """Fetch structured JSON, JSON-LD Person blocks, or HTML cards from a permitted public URL.

    Enforces blocked-domain checks (no LinkedIn scraping) and respects robots.txt before fetching.
    Never attempts to bypass authentication walls, paywalls, or anti-bot challenges.
    """
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    if is_restricted_social_url(url):
        raise PermissionError("Restricted social domain is blocked by compliance policy.")

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        r_resp = _safe_http_get_no_restricted_redirects(robots_url, timeout_s=5.0)
        if r_resp.status_code == 200:
            path_q = parsed.path or "/"
            if not _is_allowed_by_robots(r_resp.text, path_q):
                raise PermissionError(f"robots.txt disallows automated access to {url}")
    except PermissionError:
        raise
    except Exception:
        # Proceed cautiously if robots.txt endpoint is absent on a permitted feed
        pass

    resp = _safe_http_get_no_restricted_redirects(url, timeout_s=timeout_s)
    if resp.status_code in (401, 403):
        raise PermissionError(f"Target URL requires authentication or denied access ({resp.status_code}).")
    resp.raise_for_status()
    final_url = str(resp.url)
    if is_restricted_social_url(final_url):
        raise PermissionError("Restricted social domain is blocked by compliance policy.")

    lower_body = resp.text[:8000].lower()
    if any(
        gate in lower_body
        for gate in ("cf-turnstile", "g-recaptcha", "h-captcha", "verify you are human")
    ):
        raise PermissionError("Target URL presents an anti-bot or CAPTCHA challenge and cannot be accessed automatically.")

    content_type = (resp.headers.get("content-type") or "").lower()
    if "json" in content_type or resp.text.lstrip().startswith(("[", "{")):
        data = resp.json()
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            items = (
                data.get("items")
                or data.get("results")
                or data.get("profiles")
                or data.get("people")
                or data.get("speakers")
                or data.get("members")
            )
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
            if data.get("name") or data.get("full_name"):
                return [data]
        return []

    # 1. Extract schema.org Person JSON-LD blocks from official school / directory pages
    extracted: list[dict[str, Any]] = []
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        resp.text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in blocks:
        try:
            ld = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        nodes = ld if isinstance(ld, list) else (ld.get("@graph", [ld]) if isinstance(ld, dict) else [])
        for node in nodes:
            if not isinstance(node, dict):
                continue
            if node.get("@type") == "Person" and node.get("name"):
                works_for = node.get("worksFor")
                org_name = works_for.get("name") if isinstance(works_for, dict) else works_for
                same_as = node.get("sameAs")
                li_url = None
                for link in (same_as if isinstance(same_as, list) else [same_as]):
                    cleaned_li = clean_linkedin_profile_url(link) if isinstance(link, str) else None
                    if cleaned_li:
                        li_url = cleaned_li
                        break
                extracted.append(
                    {
                        "name": node.get("name"),
                        "title": node.get("jobTitle"),
                        "organization": org_name,
                        "linkedin_url": li_url,
                        "bio": node.get("description"),
                        "page_url": node.get("url") or url,
                        "source_url": final_url,
                        "verified": final_url.startswith("https://"),
                    }
                )
    if extracted:
        return extracted

    # 2. Parse semantic HTML leadership / team / speaker cards strictly from visible DOM tree
    return _extract_html_profiles(resp.text, final_url)


_NON_PERSON_PHRASES = (
    "meet our team",
    "our team",
    "read more",
    "view more",
    "learn more",
    "load more",
    "apply for",
    "about us",
    "contact us",
    "we are here",
    "conference speakers",
    "board of",
    "national council",
    "management team",
    "advisory body",
    "privacy policy",
    "cookie policy",
    "follow us",
    "executive members",
    "founding members",
    "higher education speakers",
    "school education speakers",
    "counselor conference",
    "the people guiding",
    "part of a wider",
    "what will education",
    "why this conversation",
    "dialogue, practical insight",
    "educating for",
    "our offices",
    "designed & developed",
    "developed by",
    "all rights reserved",
    "digital agency",
    "become a",
    "sponsor",
    "problem rooms",
    "what we'd",
    "do differently",
    "request a",
    "call back",
    "callback",
    "get in touch",
    "apply now",
    "know more",
    "book a",
    "register now",
    "sign up",
    "subscribe",
    "privacy",
    "terms of use",
)

_ORG_ONLY_TOKENS = {
    "ventures",
    "worldwide",
    "workshops",
    "interactive",
    "solutions",
    "technologies",
    "consulting",
    "consultancy",
    "inc",
    "llc",
    "ltd",
    "pvt",
    "corp",
    "services",
    "eduthon",
}

_ROLE_HEADING_TOKENS = {
    "founder",
    "co-founder",
    "cofounder",
    "director",
    "partner",
    "principal",
    "headmaster",
    "headmistress",
    "chairman",
    "chairperson",
    "president",
    "vice",
    "ceo",
    "cfo",
    "cto",
    "coo",
    "head",
    "manager",
    "trainer",
    "mentor",
    "advisor",
    "adviser",
    "trustee",
    "dean",
    "coordinator",
    "educator",
    "consultant",
    "asst",
    "assistant",
    "hr",
    "marketing",
    "operations",
    "academics",
    "academic",
    "finance",
    "research",
    "human",
    "resource",
    "resources",
    "child",
    "protection",
    "workplace",
    "safety",
    "defence",
    "defense",
    "keynote",
    "moderator",
    "speaker",
    "speakers",
    "panelist",
    "panellist",
    "sr",
    "financial",
    "modelling",
    "modeling",
    "panel",
    "chief",
    "executive",
    "operating",
    "technology",
    "deputy",
    "secretary",
    "treasurer",
    "officer",
}

_ROLE_SIGNAL_WORDS = {
    "principal",
    "director",
    "founder",
    "cofounder",
    "co-founder",
    "chief",
    "executive",
    "operating",
    "technology",
    "deputy",
    "secretary",
    "treasurer",
    "chairman",
    "chairperson",
    "president",
    "ceo",
    "head",
    "dean",
    "advisor",
    "adviser",
    "consultant",
    "trustee",
    "partner",
    "manager",
    "trainer",
    "mentor",
    "educator",
    "coordinator",
    "headmaster",
    "headmistress",
    "superintendent",
    "provost",
    "officer",
    "curriculum",
    "professor",
    "fellow",
}

_UI_NOISE_TEXTS = {
    "read more",
    "read more +",
    "view more",
    "learn more",
    "load more",
    "view profile",
    "connect",
    "linkedin",
    "email",
    "share",
}


class _DOMNode:
    __slots__ = ("tag", "attrs", "parent", "children", "own_text")

    def __init__(self, tag: str, attrs: dict[str, str], parent: Optional["_DOMNode"] = None) -> None:
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children: list[_DOMNode] = []
        self.own_text: list[str] = []

    def full_text(self) -> str:
        parts: list[str] = []
        if self.own_text:
            parts.append(" ".join(self.own_text))
        for child in self.children:
            ct = child.full_text()
            if ct:
                parts.append(ct)
        return normalize_whitespace(" ".join(parts))

    @property
    def cls(self) -> str:
        return self.attrs.get("class", "").lower()


class _DOMTreeBuilder(HTMLParser):
    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img",
        "input", "link", "meta", "param", "source", "track", "wbr",
    }
    _SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "footer"}

    def __init__(self) -> None:
        super().__init__()
        self.root = _DOMNode("root", {})
        self.cur = self.root
        self._skip_depth = 0
        self.title_chunks: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if tag == "title":
            self._in_title = True
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        node = _DOMNode(tag, attr_map, self.cur)
        self.cur.children.append(node)
        if tag not in self._VOID_TAGS:
            self.cur = node

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._skip_depth > 0:
            return
        if tag == "title":
            self._in_title = False
            return
        p: Optional[_DOMNode] = self.cur
        while p is not None and p is not self.root:
            if p.tag == tag:
                self.cur = p.parent or self.root
                break
            p = p.parent

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_chunks.append(data)
            return
        if self._skip_depth == 0 and data.strip():
            self.cur.own_text.append(data.strip())


def _is_plausible_person_name(raw_name: str) -> bool:
    cleaned = re.sub(r"[\u200b-\u200d\ufeff]", "", normalize_whitespace(raw_name))
    if not cleaned or len(cleaned) < 4 or len(cleaned) > 75:
        return False
    lower = cleaned.lower()
    if any(phrase in lower for phrase in _NON_PERSON_PHRASES):
        return False
    if lower in _UI_NOISE_TEXTS or any(ch.isdigit() for ch in cleaned):
        return False
    if cleaned.endswith(("?", ":", "!", "+")):
        return False
    # Reject English UI/prose contractions like "we'd", "what's", "don't"
    if re.search(r"(?:'d|'s|'t|'re|'ll|'ve)\b", lower):
        return False
    words = [w for w in re.split(r"\s+", cleaned) if w]
    if not (2 <= len(words) <= 7):
        return False
    alpha_tokens = [re.sub(r"[^a-z]", "", w.lower()) for w in words]
    alpha_tokens = [t for t in alpha_tokens if t]
    if len(alpha_tokens) < 2:
        return False
    if any(tok in _ORG_ONLY_TOKENS for tok in alpha_tokens):
        return False
    # Reject job-title headings like "Head - Human Resource" inside multi-heading Elementor cards
    if all(tok in _ROLE_HEADING_TOKENS for tok in alpha_tokens):
        return False
    if not any(w[0].isupper() for w in words if w[0].isalpha()):
        return False
    return True


def _split_inline_role_suffix(raw_name: str) -> tuple[str, Optional[str], Optional[str]]:
    """Separate inline role/org suffixes accidentally embedded inside anchor titles (e.g. 'Name CEO, Org')."""
    m = re.match(
        r"^([A-Z][A-Za-z.\-]+(?:\s+[A-Z][A-Za-z.\-]+){1,3})\s+(CEO|COO|CFO|CTO),\s*(.+)$",
        normalize_whitespace(raw_name),
    )
    if m:
        return m.group(1), m.group(2), normalize_whitespace(m.group(3))
    return raw_name, None, None


def _derive_default_org(raw_title: str, source_url: str) -> str:
    generic = {
        "team", "our team", "meet our team", "leadership", "board",
        "board of advisors", "advisory body", "national council",
        "management team", "faculty", "speakers", "about", "about us", "home",
    }
    if raw_title:
        segments = [normalize_whitespace(seg) for seg in re.split(r"\s*[|\-–—:]\s*", raw_title) if normalize_whitespace(seg)]
        for seg in segments:
            cleaned = re.sub(r"^(?:team|leadership|board|about)\s+(?:at|of)\s+", "", seg, flags=re.I).strip()
            if cleaned.lower() not in generic and len(cleaned) >= 3:
                return cleaned
    return urlparse(source_url).netloc


def _looks_like_role(text: str) -> bool:
    if not text or len(text) > 100 or len(text.split()) > 9 or text.endswith("."):
        return False
    words = {re.sub(r"[^a-z\-]", "", w.lower()) for w in text.split()}
    return bool(words & _ROLE_SIGNAL_WORDS)


def _split_org_and_location(org_text: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not org_text:
        return None, None
    cleaned_org = re.sub(r"\s+,", ",", normalize_whitespace(org_text)).rstrip(" ,;")
    if not cleaned_org:
        return None, None
    m = re.match(r"^(.{4,}?),\s*([A-Z][A-Za-z.\s]{1,28})$", cleaned_org)
    if m:
        candidate_loc = normalize_whitespace(m.group(2)).strip(".,;: ")
        loc_lower = candidate_loc.lower()
        if candidate_loc and not any(
            tok in loc_lower for tok in ("school", "academy", "foundation", "trust", "university", "group", "ltd", "inc")
        ):
            return cleaned_org, candidate_loc
    return cleaned_org, None


def _extract_role_from_bio(name: str, bio: str) -> Optional[str]:
    if not bio:
        return None
    m = re.search(
        r"\b(?:is|serves as|was)\s+(?:the|an|a)\s+([A-Z][A-Za-z&\-\s]{2,55}?)\s+(?:of|at|to|for)\b",
        bio,
    )
    if m:
        candidate = normalize_whitespace(m.group(1)).rstrip(".,;:")
        if _looks_like_role(candidate) and candidate.lower() not in name.lower():
            return candidate
    return None


def _extract_html_profiles(html_text: str, source_url: str) -> list[dict[str, Any]]:
    builder = _DOMTreeBuilder()
    builder.feed(html_text)
    raw_title = normalize_whitespace("".join(builder.title_chunks))
    default_org = _derive_default_org(raw_title, source_url)

    # Identify candidate person heading/title nodes
    candidate_nodes: list[tuple[_DOMNode, str]] = []

    def find_person_nodes(node: _DOMNode) -> None:
        is_heading = node.tag in ("h2", "h3", "h4", "h5")
        is_card_title_link = (
            node.tag in ("a", "strong", "b")
            and any(k in node.cls for k in ("title", "name", "speaker", "leader", "member", "person"))
        )
        if is_heading or is_card_title_link:
            txt = re.sub(r"[\u200b-\u200d\ufeff]", "", node.full_text())
            if _is_plausible_person_name(txt):
                candidate_nodes.append((node, txt))
                return
        for child in node.children:
            find_person_nodes(child)

    find_person_nodes(builder.root)
    if not candidate_nodes:
        return []

    person_node_ids = {id(node) for node, _ in candidate_nodes}

    def count_person_nodes_in_subtree(node: _DOMNode) -> int:
        cnt = 1 if id(node) in person_node_ids else 0
        for child in node.children:
            cnt += count_person_nodes_in_subtree(child)
        return cnt

    profiles: list[dict[str, Any]] = []
    seen_names: set[str] = set()

    for pnode, raw_cand_name in candidate_nodes:
        cand_name, inline_role, inline_org = _split_inline_role_suffix(raw_cand_name)
        norm_key = normalize_person_name(cand_name)
        if not norm_key or norm_key in seen_names:
            continue

        # Walk upward to the outermost single-person card container (strictly 1 person node)
        best_card: Optional[_DOMNode] = None
        anc = pnode.parent
        for _ in range(5):
            if anc is None or anc.tag in ("body", "html", "root"):
                break
            if count_person_nodes_in_subtree(anc) == 1 and len(anc.full_text()) <= 2500:
                best_card = anc
                anc = anc.parent
            else:
                break
        if best_card is None:
            continue

        role: Optional[str] = inline_role
        org: Optional[str] = inline_org
        location: Optional[str] = None
        tag_labels: list[str] = []
        bio_parts: list[str] = []
        short_fragments: list[tuple[str, str, str]] = []
        li_links: set[str] = set()

        def collect_li_links(node: _DOMNode) -> None:
            if node.tag == "a":
                cleaned_li = clean_linkedin_profile_url(node.attrs.get("href"))
                if cleaned_li:
                    li_links.add(cleaned_li)
            for c in node.children:
                collect_li_links(c)

        collect_li_links(best_card)

        def collect_card_fields(node: _DOMNode) -> None:
            nonlocal role, org, location
            if node is pnode:
                return

            has_block_children = any(
                c.tag in ("div", "p", "h1", "h2", "h3", "h4", "h5", "ul", "li", "article", "section", "blockquote")
                for c in node.children
            )
            if node.tag in ("h2", "h3", "h4", "h5", "p", "span", "strong", "blockquote") or (
                node.tag == "div" and not has_block_children
            ):
                if node.tag in ("span", "div") and has_block_children:
                    for c in node.children:
                        collect_card_fields(c)
                    return
                if (
                    len(node.children) == 1
                    and node.children[0].tag == "a"
                    and clean_linkedin_profile_url(node.children[0].attrs.get("href"))
                ):
                    return
                txt = re.sub(r"[\u200b-\u200d\ufeff]", "", node.full_text())
                if not txt or txt.lower() in _UI_NOISE_TEXTS or txt == raw_cand_name or txt == cand_name:
                    for c in node.children:
                        collect_card_fields(c)
                    return

                cls = node.cls
                is_sentence = len(txt.split()) >= 12 or (txt.endswith(".") and len(txt) > 55)
                if any(k in cls for k in ("location", "city", "country")) and not location and len(txt) <= 80:
                    location = txt
                elif any(k in cls for k in ("role", "title", "designation", "position", "subtitle")) and not role and not txt.endswith(".") and len(txt) <= 135:
                    role = txt
                elif any(k in cls for k in ("org", "school", "company", "institution", "affiliation")) and not org and not is_sentence and len(txt) <= 140:
                    org = txt
                elif any(k in cls for k in ("tag", "badge", "chip")) and len(txt) <= 50:
                    tag_labels.append(txt)
                elif node.tag in ("h2", "h3", "h4", "h5") and not role and not is_sentence and len(txt) <= 120:
                    role = txt
                elif is_sentence or len(txt) > 95:
                    if txt not in bio_parts:
                        bio_parts.append(txt)
                else:
                    short_fragments.append((node.tag, cls, txt))
                return

            for c in node.children:
                collect_card_fields(c)

        collect_card_fields(best_card)

        for tag, _cls, txt in short_fragments:
            if not role and _looks_like_role(txt):
                role = txt
            elif not org and role and txt != role and len(txt) <= 140:
                org = txt
            elif not bio_parts and len(txt) >= 35 and txt != role and txt != org:
                bio_parts.append(txt)
            elif len(txt) > 50 and txt not in bio_parts and txt != role and txt != org:
                bio_parts.append(txt)

        bio = " ".join(bio_parts[:2]) if bio_parts else None
        if not role and bio:
            role = _extract_role_from_bio(cand_name, bio)
        # Skip empty/nav CTA blocks lacking both role and biographical evidence
        if not role and (not bio or len(bio) < 35):
            continue

        parsed_org, extracted_loc = _split_org_and_location(org)
        if extracted_loc and not location:
            location = extracted_loc

        seen_names.add(norm_key)
        profiles.append(
            {
                "name": cand_name,
                "title": role,
                "organization": parsed_org or default_org,
                "location": location,
                "bio": bio or ("; ".join(tag_labels) if tag_labels else None),
                "linkedin_url": next(iter(li_links)) if len(li_links) == 1 else None,
                "influence_indicators": tag_labels,
                "page_url": source_url,
                "source_url": source_url,
                "verified": source_url.startswith("https://"),
            }
        )
    return profiles
