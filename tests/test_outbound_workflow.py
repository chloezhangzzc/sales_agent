from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from main import render_company_draft_report
from sales_agent.config import OpenAISettings
from sales_agent.drafts import create_draft_from_result, create_drafts, send_approved_drafts
from sales_agent.leads import load_leads_from_csv
from sales_agent.openai_drafter import enforce_signature, sanitize_text
from sales_agent.research import research_lead


class FakeEmailService:
    def __init__(self) -> None:
        self.sent: list[tuple[list[str], str, str]] = []

    def send_email(self, to, subject, body_text, body_html=None) -> None:
        self.sent.append((list(to), subject, body_text))


class OutboundWorkflowTests(unittest.TestCase):
    def test_load_leads_from_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leads.csv"
            path.write_text(
                "company_name,website_url,contact_email,contact_name,careers_url,notes\n"
                "Acme,https://acme.example,hello@acme.example,Alice,,Hiring engineers\n",
                encoding="utf-8",
            )

            leads = load_leads_from_csv(path)

        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].company_name, "Acme")
        self.assertEqual(leads[0].contact_name, "Alice")

    def test_research_lead_discovers_careers_page(self) -> None:
        homepage_html = """
        <html>
          <head>
            <title>Acme builds developer tooling</title>
            <meta name="description" content="Acme helps product teams ship internal tools faster.">
          </head>
          <body>
            <a href="/careers">Careers</a>
            <p>We are hiring engineers and product designers.</p>
          </body>
        </html>
        """
        careers_html = """
        <html>
          <head><title>Acme Careers</title></head>
          <body><p>Open roles across engineering.</p></body>
        </html>
        """

        def fake_fetcher(url: str) -> str:
            if url == "https://acme.example":
                return homepage_html
            if url == "https://acme.example/careers":
                return careers_html
            raise AssertionError(f"Unexpected URL fetched: {url}")

        lead_csv = (
            "company_name,website_url,contact_email,contact_name,careers_url,notes\n"
            "Acme,https://acme.example,hello@acme.example,Alice,,Hiring engineers\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "leads.csv"
            path.write_text(lead_csv, encoding="utf-8")
            lead = load_leads_from_csv(path)[0]

        result = research_lead(lead, fetcher=fake_fetcher)

        self.assertEqual(result.research_status, "ok")
        self.assertEqual(result.careers_url, "https://acme.example/careers")
        self.assertIn("careers page", result.hiring_signal.lower())

    def test_research_lead_discovers_contact_email_from_contact_page(self) -> None:
        homepage_html = """
        <html>
          <head><title>Acme</title></head>
          <body>
            <a href="/contact">Contact</a>
            <p>Developer hiring platform for startups.</p>
          </body>
        </html>
        """
        contact_html = """
        <html>
          <head><title>Contact Acme</title></head>
          <body><p>Email us at team@acme.example</p></body>
        </html>
        """

        def fake_fetcher(url: str) -> str:
            if url == "https://acme.example":
                return homepage_html
            if url == "https://acme.example/contact":
                return contact_html
            raise AssertionError(f"Unexpected URL fetched: {url}")

        lead = load_leads_from_csv(
            _write_csv(
                "company_name,website_url,contact_email,contact_name,careers_url,notes\n"
                "Acme,https://acme.example,,, ,\n"
            )
        )[0]

        result = research_lead(lead, fetcher=fake_fetcher)

        self.assertEqual(result.contact_email, "team@acme.example")
        self.assertTrue(any("team@acme.example" in item for item in result.evidence))

    def test_send_approved_drafts_only(self) -> None:
        research_results = [
            research_lead(
                load_leads_from_csv(
                    _write_csv(
                        "company_name,website_url,contact_email,contact_name,careers_url,notes\n"
                        "Acme,https://acme.example,hello@acme.example,Alice,,Hiring engineers\n"
                    )
                )[0],
                fetcher=lambda _url: """
                <html>
                  <head><title>Acme</title><meta name="description" content="Hiring engineers now."></head>
                  <body><a href="/careers">Careers</a></body>
                </html>
                """,
            )
        ]
        drafts = create_drafts(research_results)
        pending = drafts[0]
        approved = pending.__class__(**{**pending.__dict__, "approved": "yes"})

        service = FakeEmailService()
        updated = send_approved_drafts(service, [pending, approved], review_email="chloezzx@bu.edu")

        self.assertEqual(len(service.sent), 1)
        self.assertEqual(service.sent[0][0], ["chloezzx@bu.edu"])
        self.assertEqual(updated[0].status, "pending_review")
        self.assertEqual(updated[1].status, "sent")
        self.assertEqual(updated[1].actual_recipient_email, "chloezzx@bu.edu")

    def test_send_approved_drafts_live_goes_to_company_recipient(self) -> None:
        research_results = [
            research_lead(
                load_leads_from_csv(
                    _write_csv(
                        "company_name,website_url,contact_email,contact_name,careers_url,notes\n"
                        "Acme,https://acme.example,hello@acme.example,Alice,,Hiring engineers\n"
                    )
                )[0],
                fetcher=lambda _url: """
                <html>
                  <head><title>Acme</title><meta name="description" content="Hiring engineers now."></head>
                  <body><a href="/careers">Careers</a></body>
                </html>
                """,
            )
        ]
        approved = create_drafts(research_results)[0].__class__(
            **{**create_drafts(research_results)[0].__dict__, "approved": "yes"}
        )

        service = FakeEmailService()
        updated = send_approved_drafts(
            service,
            [approved],
            review_email="chloezzx@bu.edu",
            live_outreach_enabled=True,
        )

        self.assertEqual(service.sent[0][0], ["hello@acme.example"])
        self.assertEqual(updated[0].actual_recipient_email, "hello@acme.example")

    def test_create_draft_uses_openai_when_available(self) -> None:
        result = research_lead(
            load_leads_from_csv(
                _write_csv(
                    "company_name,website_url,contact_email,contact_name,careers_url,notes\n"
                    "Acme,https://acme.example,hello@acme.example,Alice,,Hiring engineers\n"
                )
            )[0],
            fetcher=lambda _url: """
            <html>
              <head><title>Acme</title><meta name="description" content="Hiring engineers now."></head>
              <body><a href="/careers">Careers</a></body>
            </html>
            """,
        )
        settings = OpenAISettings(api_key="sk-test", model="gpt-5")

        with patch("sales_agent.drafts.generate_email") as mock_generate_email:
            mock_generate_email.return_value.subject = "Custom subject"
            mock_generate_email.return_value.body_text = "Custom body"
            draft = create_draft_from_result(result, openai_settings=settings)

        self.assertEqual(draft.subject, "Custom subject")
        self.assertEqual(draft.body_text, "Custom body")
        self.assertEqual(draft.generation_method, "openai:gpt-5")

    def test_sanitize_text_replaces_smart_punctuation(self) -> None:
        cleaned = sanitize_text("you’re doing great - 15‑minute intro with “quotes”")
        self.assertEqual(cleaned, 'you\'re doing great - 15-minute intro with "quotes"')

    def test_enforce_signature_replaces_generated_signature(self) -> None:
        body = "Hi team,\n\nQuick note.\n\nBest,\nSamw"
        cleaned = enforce_signature(body, signature_name="Chloe")
        self.assertTrue(cleaned.endswith("Best,\nChloe"))
        self.assertNotIn("Samw", cleaned)

    def test_render_company_draft_report_includes_research_and_email(self) -> None:
        result = research_lead(
            load_leads_from_csv(
                _write_csv(
                    "company_name,website_url,contact_email,contact_name,careers_url,notes\n"
                    "Acme,https://acme.example,hello@acme.example,Alice,,Hiring engineers\n"
                )
            )[0],
            fetcher=lambda _url: """
            <html>
              <head><title>Acme</title><meta name="description" content="Hiring engineers now."></head>
              <body><a href="/careers">Careers</a></body>
            </html>
            """,
        )
        draft = create_draft_from_result(result)

        report = render_company_draft_report(result, draft, "single_company_draft.csv")

        self.assertIn("Saved 1 draft to single_company_draft.csv.", report)
        self.assertIn("Research summary:", report)
        self.assertIn("Draft subject:", report)
        self.assertIn(draft.subject, report)


def _write_csv(contents: str) -> Path:
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".csv")
    handle.write(contents)
    handle.flush()
    handle.close()
    return Path(handle.name)


if __name__ == "__main__":
    unittest.main()
