from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sales_agent.config import OpenAISettings
from sales_agent.email_service import InkboxEmailService
from sales_agent.openai_drafter import generate_email
from sales_agent.research import ResearchResult

PRODUCT_ONE_LINER = (
    "Hirepilot helps teams screen candidates faster with AI-native assessment workflows, including AI-generated "
    "OA, voice-based evaluation, and founder interview support."
)
DEFAULT_SIGNATURE_NAME = "Chloe"


@dataclass(frozen=True)
class OutreachDraft:
    approved: str
    status: str
    sent_at: str
    company_name: str
    contact_email: str
    contact_name: str
    subject: str
    body_text: str
    research_summary: str
    hiring_signal: str
    personalization_angle: str
    source_urls: str
    generation_method: str
    actual_recipient_email: str

    def to_row(self) -> dict[str, str]:
        return {
            "approved": self.approved,
            "status": self.status,
            "sent_at": self.sent_at,
            "company_name": self.company_name,
            "contact_email": self.contact_email,
            "contact_name": self.contact_name,
            "subject": self.subject,
            "body_text": self.body_text,
            "research_summary": self.research_summary,
            "hiring_signal": self.hiring_signal,
            "personalization_angle": self.personalization_angle,
            "source_urls": self.source_urls,
            "generation_method": self.generation_method,
            "actual_recipient_email": self.actual_recipient_email,
        }

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "OutreachDraft":
        return cls(
            approved=row.get("approved", "").strip(),
            status=row.get("status", "").strip(),
            sent_at=row.get("sent_at", "").strip(),
            company_name=row.get("company_name", "").strip(),
            contact_email=row.get("contact_email", "").strip(),
            contact_name=row.get("contact_name", "").strip(),
            subject=row.get("subject", "").strip(),
            body_text=row.get("body_text", "").strip(),
            research_summary=row.get("research_summary", "").strip(),
            hiring_signal=row.get("hiring_signal", "").strip(),
            personalization_angle=row.get("personalization_angle", "").strip(),
            source_urls=row.get("source_urls", "").strip(),
            generation_method=row.get("generation_method", "").strip() or "template",
            actual_recipient_email=row.get("actual_recipient_email", "").strip(),
        )


def build_subject(result: ResearchResult) -> str:
    if "careers page" in result.hiring_signal.lower() or "hiring" in result.hiring_signal.lower():
        return f"{result.company_name}'s hiring workflow"
    return f"A quick idea for {result.company_name}"


def build_opening(result: ResearchResult) -> str:
    if result.contact_name:
        opener = f"Hi {result.contact_name},"
    else:
        opener = "Hi,"

    if result.summary:
        return f"{opener}\n\nI spent a little time looking through {result.company_name}'s site"
    return f"{opener}\n\nI came across {result.company_name}"


def build_body_text(result: ResearchResult) -> str:
    opening = build_opening(result)
    summary_line = f" and saw that {result.summary.lower().rstrip('.')}" if result.summary else "."
    if result.summary and summary_line.endswith(".."):
        summary_line = summary_line[:-1]

    body = (
        f"{opening}{summary_line}.\n\n"
        f"I'm reaching out from Hirepilot. {PRODUCT_ONE_LINER}\n\n"
        f"What stood out to me was this angle: {result.personalization_angle}\n\n"
        f"If helpful, I can share how teams use this to reduce manual screening time while giving founders a more "
        f"structured way to evaluate candidates.\n\n"
        f"Open to a short conversation?\n\n"
        f"Best,\n{DEFAULT_SIGNATURE_NAME}"
    )
    return body.replace("..", ".")


def create_draft_from_result(
    result: ResearchResult,
    openai_settings: OpenAISettings | None = None,
) -> OutreachDraft:
    subject = build_subject(result)
    body_text = build_body_text(result)
    generation_method = "template"

    if openai_settings is not None:
        try:
            generated = generate_email(result, openai_settings)
            subject = generated.subject
            body_text = generated.body_text
            generation_method = f"openai:{openai_settings.model}"
        except Exception:
            generation_method = "template_fallback"

    return OutreachDraft(
        approved="no",
        status="pending_review",
        sent_at="",
        company_name=result.company_name,
        contact_email=result.contact_email,
        contact_name=result.contact_name,
        subject=subject,
        body_text=body_text,
        research_summary=result.summary,
        hiring_signal=result.hiring_signal,
        personalization_angle=result.personalization_angle,
        source_urls=", ".join(result.source_urls),
        generation_method=generation_method,
        actual_recipient_email="",
    )


def create_drafts(
    results: list[ResearchResult],
    openai_settings: OpenAISettings | None = None,
) -> list[OutreachDraft]:
    drafts: list[OutreachDraft] = []
    for result in results:
        drafts.append(create_draft_from_result(result, openai_settings=openai_settings))
    return drafts


def save_drafts_csv(path: str | Path, drafts: list[OutreachDraft]) -> None:
    rows = [draft.to_row() for draft in drafts]
    fieldnames = list(rows[0].keys()) if rows else [
        "approved",
        "status",
        "sent_at",
        "company_name",
        "contact_email",
        "contact_name",
        "subject",
        "body_text",
        "research_summary",
        "hiring_signal",
        "personalization_angle",
        "source_urls",
        "generation_method",
        "actual_recipient_email",
    ]
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_drafts_csv(path: str | Path) -> list[OutreachDraft]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [OutreachDraft.from_row(row) for row in reader]


def is_approved(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1", "approved"}


def send_approved_drafts(
    service: InkboxEmailService,
    drafts: list[OutreachDraft],
    review_email: str,
    live_outreach_enabled: bool = False,
) -> list[OutreachDraft]:
    updated: list[OutreachDraft] = []
    for draft in drafts:
        if draft.status == "sent":
            updated.append(draft)
            continue

        if not is_approved(draft.approved):
            updated.append(draft)
            continue

        recipient_email = draft.contact_email if live_outreach_enabled and draft.contact_email else review_email
        service.send_email(
            to=[recipient_email],
            subject=draft.subject,
            body_text=draft.body_text,
        )
        updated.append(
            OutreachDraft(
                approved=draft.approved,
                status="sent",
                sent_at=datetime.now(timezone.utc).isoformat(),
                company_name=draft.company_name,
                contact_email=draft.contact_email,
                contact_name=draft.contact_name,
                subject=draft.subject,
                body_text=draft.body_text,
                research_summary=draft.research_summary,
                hiring_signal=draft.hiring_signal,
                personalization_angle=draft.personalization_angle,
                source_urls=draft.source_urls,
                generation_method=draft.generation_method,
                actual_recipient_email=recipient_email,
            )
        )
    return updated
