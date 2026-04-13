from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from sales_agent.leads import Lead

DEFAULT_TIMEOUT_SECONDS = 15
USER_AGENT = "Mozilla/5.0 (compatible; HirepilotOutreachBot/0.1; +https://inkbox.ai)"
HIRING_KEYWORDS = (
    "career",
    "careers",
    "job",
    "jobs",
    "hiring",
    "open role",
    "open roles",
    "join our team",
    "work with us",
    "apply now",
)
CONTACT_PAGE_KEYWORDS = ("contact", "about", "team", "people", "company", "careers", "jobs")
EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", flags=re.IGNORECASE)


@dataclass(frozen=True)
class PageSnapshot:
    url: str
    title: str
    meta_description: str
    text_excerpt: str
    links: list[str]


@dataclass(frozen=True)
class ResearchResult:
    company_name: str
    website_url: str
    contact_email: str
    contact_name: str
    careers_url: str
    summary: str
    hiring_signal: str
    personalization_angle: str
    evidence: list[str]
    source_urls: list[str]
    research_status: str
    notes: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "ResearchResult":
        return cls(
            company_name=str(payload.get("company_name", "")),
            website_url=str(payload.get("website_url", "")),
            contact_email=str(payload.get("contact_email", "")),
            contact_name=str(payload.get("contact_name", "")),
            careers_url=str(payload.get("careers_url", "")),
            summary=str(payload.get("summary", "")),
            hiring_signal=str(payload.get("hiring_signal", "")),
            personalization_angle=str(payload.get("personalization_angle", "")),
            evidence=[str(item) for item in payload.get("evidence", [])],
            source_urls=[str(item) for item in payload.get("source_urls", [])],
            research_status=str(payload.get("research_status", "")),
            notes=str(payload.get("notes", "")),
        )


def fetch_page(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8", errors="ignore")


def extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return collapse_whitespace(unescape(strip_tags(match.group(1))))


def extract_meta_description(html: str) -> str:
    match = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""
    return collapse_whitespace(unescape(match.group(1)))


def strip_tags(html: str) -> str:
    without_scripts = re.sub(r"<script.*?>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    without_styles = re.sub(r"<style.*?>.*?</style>", " ", without_scripts, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_styles)
    return unescape(without_tags)


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_text_excerpt(html: str, max_chars: int = 700) -> str:
    text = collapse_whitespace(strip_tags(html))
    return text[:max_chars].strip()


def extract_links(base_url: str, html: str) -> list[str]:
    links = []
    for match in re.finditer(r"<a[^>]+href=[\"'](.*?)[\"']", html, flags=re.IGNORECASE | re.DOTALL):
        href = match.group(1).strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        links.append(urljoin(base_url, href))

    deduped: list[str] = []
    seen: set[str] = set()
    for link in links:
        if link not in seen:
            deduped.append(link)
            seen.add(link)
    return deduped


def extract_emails(html: str) -> list[str]:
    emails = [match.group(0).strip(".,;:()[]{}<>\"'") for match in EMAIL_PATTERN.finditer(html)]
    deduped: list[str] = []
    seen: set[str] = set()
    for email in emails:
        lowered = email.lower()
        if lowered not in seen:
            deduped.append(email)
            seen.add(lowered)
    return deduped


def same_domain(url_a: str, url_b: str) -> bool:
    host_a = urlparse(url_a).netloc.lower()
    host_b = urlparse(url_b).netloc.lower()
    return bool(host_a and host_b and host_a == host_b)


def snapshot_page(url: str, fetcher: Callable[[str], str] = fetch_page) -> PageSnapshot:
    html = fetcher(url)
    return PageSnapshot(
        url=url,
        title=extract_title(html),
        meta_description=extract_meta_description(html),
        text_excerpt=extract_text_excerpt(html),
        links=extract_links(url, html),
    )


def discover_careers_url(lead: Lead, homepage: PageSnapshot) -> str:
    if lead.careers_url:
        return lead.careers_url

    for link in homepage.links:
        lowered = link.lower()
        if any(keyword in lowered for keyword in ("career", "careers", "jobs", "hiring")):
            return link
    return ""


def discover_contact_page_urls(homepage: PageSnapshot, careers_url: str) -> list[str]:
    candidates: list[str] = []
    for link in homepage.links:
        lowered = link.lower()
        if not same_domain(homepage.url, link):
            continue
        if any(keyword in lowered for keyword in CONTACT_PAGE_KEYWORDS):
            candidates.append(link)

    if careers_url and same_domain(homepage.url, careers_url):
        candidates.append(careers_url)

    deduped: list[str] = []
    seen: set[str] = set()
    for link in candidates:
        if link not in seen:
            deduped.append(link)
            seen.add(link)
        if len(deduped) >= 5:
            break
    return deduped


def discover_contact_email(
    lead: Lead,
    homepage: PageSnapshot,
    careers_url: str,
    fetcher: Callable[[str], str] = fetch_page,
) -> tuple[str, list[str], list[str]]:
    if lead.contact_email:
        return lead.contact_email, [], [f"Using provided contact email: {lead.contact_email}"]

    homepage_emails = extract_emails(homepage.text_excerpt + " " + " ".join(homepage.links))
    if homepage_emails:
        email = homepage_emails[0]
        return email, [], [f"Found contact email on homepage: {email}"]

    visited_urls: list[str] = []
    evidence: list[str] = []
    for url in discover_contact_page_urls(homepage, careers_url):
        try:
            page = snapshot_page(url, fetcher=fetcher)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            evidence.append(f"Contact page fetch failed: {url} ({exc})")
            continue

        visited_urls.append(page.url)
        page_emails = extract_emails(f"{page.title} {page.meta_description} {page.text_excerpt}")
        if page_emails:
            email = page_emails[0]
            evidence.append(f"Found contact email on {page.url}: {email}")
            return email, visited_urls, evidence

    return "", visited_urls, evidence


def detect_hiring_signal(texts: list[str], careers_url: str) -> str:
    combined = " ".join(texts).lower()
    if careers_url:
        return f"Has a public careers page: {careers_url}"

    for keyword in HIRING_KEYWORDS:
        if keyword in combined:
            return f"Website mentions hiring-related language such as '{keyword}'."

    return "No explicit hiring page found; outreach should stay exploratory rather than assuming active hiring."


def build_summary(company_name: str, homepage: PageSnapshot, careers_page: PageSnapshot | None) -> str:
    parts = [part for part in (homepage.meta_description, homepage.title, homepage.text_excerpt) if part]
    if careers_page and careers_page.meta_description:
        parts.append(f"Careers page: {careers_page.meta_description}")
    combined = " ".join(parts)
    if not combined:
        return f"{company_name} website was reachable, but there was not enough readable text for a detailed summary."
    return combined[:420].strip()


def build_personalization_angle(lead: Lead, summary: str, hiring_signal: str) -> str:
    lower_summary = summary.lower()
    if "engineer" in lower_summary or "developer" in lower_summary or "technical" in lower_summary:
        return (
            "Lead with engineering-hiring relevance: faster screening, AI-generated OA, and better signal on how "
            "candidates perform when AI assistance is available."
        )
    if "founder" in lower_summary or "startup" in lower_summary or "small team" in lower_summary:
        return (
            "Lead with founder efficiency: help lean teams screen faster and give founders interview support with "
            "AI-generated questions and evaluation summaries."
        )
    if "hiring" in hiring_signal.lower() or "careers" in hiring_signal.lower():
        return (
            "Lead with active recruiting momentum: position the product as a way to reduce screening workload and "
            "standardize early-stage candidate evaluation."
        )
    if lead.notes:
        return f"Lead with the operator note you already captured: {lead.notes}"
    return (
        "Lead with a short exploratory message focused on how Hirepilot helps teams screen candidates, generate "
        "AI-native OA workflows, and support founder interviews."
    )


def research_lead(lead: Lead, fetcher: Callable[[str], str] = fetch_page) -> ResearchResult:
    evidence: list[str] = []
    source_urls: list[str] = []
    homepage = None
    careers_page = None

    try:
        homepage = snapshot_page(lead.website_url, fetcher=fetcher)
        source_urls.append(homepage.url)
        if homepage.title:
            evidence.append(f"Homepage title: {homepage.title}")
        if homepage.meta_description:
            evidence.append(f"Homepage meta description: {homepage.meta_description}")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        return ResearchResult(
            company_name=lead.company_name,
            website_url=lead.website_url,
            contact_email=lead.contact_email,
            contact_name=lead.contact_name,
            careers_url=lead.careers_url,
            summary=f"Could not fetch website content: {exc}",
            hiring_signal="Unknown",
            personalization_angle="Use a generic exploratory outreach note.",
            evidence=[f"Homepage fetch failed: {exc}"],
            source_urls=[],
            research_status="failed",
            notes=lead.notes,
        )

    careers_url = discover_careers_url(lead, homepage)
    if careers_url:
        try:
            careers_page = snapshot_page(careers_url, fetcher=fetcher)
            source_urls.append(careers_page.url)
            if careers_page.title:
                evidence.append(f"Careers page title: {careers_page.title}")
            if careers_page.meta_description:
                evidence.append(f"Careers page meta description: {careers_page.meta_description}")
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            evidence.append(f"Careers page fetch failed: {exc}")

    contact_email, contact_source_urls, contact_evidence = discover_contact_email(
        lead,
        homepage=homepage,
        careers_url=careers_url,
        fetcher=fetcher,
    )
    source_urls.extend(contact_source_urls)
    evidence.extend(contact_evidence)

    summary = build_summary(lead.company_name, homepage, careers_page)
    hiring_signal = detect_hiring_signal(
        [
            homepage.title,
            homepage.meta_description,
            homepage.text_excerpt,
            careers_page.title if careers_page else "",
            careers_page.meta_description if careers_page else "",
            careers_page.text_excerpt if careers_page else "",
        ],
        careers_url=careers_url,
    )
    personalization_angle = build_personalization_angle(lead, summary=summary, hiring_signal=hiring_signal)

    return ResearchResult(
        company_name=lead.company_name,
        website_url=lead.website_url,
        contact_email=contact_email,
        contact_name=lead.contact_name,
        careers_url=careers_url,
        summary=summary,
        hiring_signal=hiring_signal,
        personalization_angle=personalization_angle,
        evidence=evidence[:8],
        source_urls=source_urls,
        research_status="ok",
        notes=lead.notes,
    )


def research_leads(leads: list[Lead], fetcher: Callable[[str], str] = fetch_page) -> list[ResearchResult]:
    return [research_lead(lead, fetcher=fetcher) for lead in leads]


def save_research_results(path: str | Path, results: list[ResearchResult]) -> None:
    payload = [result.to_dict() for result in results]
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_research_results(path: str | Path) -> list[ResearchResult]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ResearchResult.from_dict(item) for item in payload]
