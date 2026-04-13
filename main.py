from __future__ import annotations

import argparse
from pathlib import Path

from sales_agent.config import InkboxSettings, OpenAISettings
from sales_agent.drafts import (
    create_draft_from_result,
    create_drafts,
    load_drafts_csv,
    save_drafts_csv,
    send_approved_drafts,
)
from sales_agent.email_service import InkboxEmailService
from sales_agent.leads import Lead, load_leads_from_csv
from sales_agent.research import load_research_results, research_lead, research_leads, save_research_results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send email through an Inkbox-backed agent identity.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap", help="Create the configured Inkbox identity if it does not exist."
    )
    bootstrap_parser.set_defaults(handler=handle_bootstrap)

    send_parser = subparsers.add_parser("send", help="Send an email from the configured Inkbox identity.")
    send_parser.add_argument("--to", nargs="+", required=True, help="Recipient email address(es).")
    send_parser.add_argument("--subject", required=True, help="Email subject.")
    send_parser.add_argument("--body", help="Plain text email body.")
    send_parser.add_argument("--body-file", help="Path to a file containing the plain text email body.")
    send_parser.add_argument("--body-html", help="Optional HTML email body.")
    send_parser.add_argument("--body-html-file", help="Path to a file containing the HTML email body.")
    send_parser.set_defaults(handler=handle_send)

    intro_parser = subparsers.add_parser(
        "send-intro", help="Send the default introduction email for the assigned outreach agent."
    )
    intro_parser.add_argument("--to", default="chloezzx@bu.edu", help="Recipient email address.")
    intro_parser.set_defaults(handler=handle_send_intro)

    research_parser = subparsers.add_parser(
        "research-leads", help="Research company websites from a CSV and save structured notes as JSON."
    )
    research_parser.add_argument("--input", required=True, help="CSV file with lead rows.")
    research_parser.add_argument(
        "--output",
        default="research_results.json",
        help="Output JSON file for structured research notes.",
    )
    research_parser.set_defaults(handler=handle_research_leads)

    draft_parser = subparsers.add_parser(
        "draft-emails",
        help="Turn saved research notes into outreach drafts for manual review.",
    )
    draft_parser.add_argument("--research-file", required=True, help="JSON file produced by research-leads.")
    draft_parser.add_argument(
        "--output",
        default="outreach_drafts.csv",
        help="Output CSV file containing drafts and approval columns.",
    )
    draft_parser.set_defaults(handler=handle_draft_emails)

    send_approved_parser = subparsers.add_parser(
        "send-approved",
        help="Send only approved outreach drafts and write status updates back to the CSV.",
    )
    send_approved_parser.add_argument("--drafts-file", required=True, help="Draft CSV file to read and update.")
    send_approved_parser.add_argument(
        "--live",
        action="store_true",
        help="Send to the discovered company recipient instead of the configured review inbox.",
    )
    send_approved_parser.set_defaults(handler=handle_send_approved)

    company_parser = subparsers.add_parser(
        "draft-company",
        help="Research one company from its name and website, then generate a personalized draft.",
    )
    company_parser.add_argument("--company-name", required=True, help="Target company name.")
    company_parser.add_argument("--website-url", required=True, help="Target company website.")
    company_parser.add_argument("--contact-email", default="", help="Optional recipient email address.")
    company_parser.add_argument("--contact-name", default="", help="Optional contact name.")
    company_parser.add_argument("--careers-url", default="", help="Optional known careers page URL.")
    company_parser.add_argument("--notes", default="", help="Optional operator notes for personalization.")
    company_parser.add_argument(
        "--output",
        default="single_company_draft.csv",
        help="Output CSV file containing the generated draft.",
    )
    company_parser.set_defaults(handler=handle_draft_company)

    return parser


def load_body(args: argparse.Namespace) -> str:
    if args.body and args.body_file:
        raise ValueError("Use either --body or --body-file, not both")

    if args.body:
        return args.body

    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")

    raise ValueError("One of --body or --body-file is required")


def load_body_html(args: argparse.Namespace) -> str | None:
    if args.body_html and args.body_html_file:
        raise ValueError("Use either --body-html or --body-html-file, not both")

    if args.body_html:
        return args.body_html

    if args.body_html_file:
        return Path(args.body_html_file).read_text(encoding="utf-8")

    return None


def handle_bootstrap(_: argparse.Namespace) -> None:
    service = InkboxEmailService(InkboxSettings.from_env())
    service.bootstrap_identity()
    print("Inkbox identity is ready.")


def handle_send(args: argparse.Namespace) -> None:
    service = InkboxEmailService(InkboxSettings.from_env())
    body = load_body(args)
    body_html = load_body_html(args)
    service.send_email(
        to=args.to,
        subject=args.subject,
        body_text=body,
        body_html=body_html,
    )
    print("Email sent.")


def handle_send_intro(args: argparse.Namespace) -> None:
    settings = InkboxSettings.from_env()
    service = InkboxEmailService(settings)
    service.send_email(
        to=[args.to],
        subject=f"Hello from @{settings.identity_handle}",
        body_text=(
            f"Hey zhixin!\n\n"
            f"I'm @{settings.identity_handle}, the Inkbox AI agent assigned to this session.\n\n"
            f"My email address is {settings.identity_email} and I'm set up and ready to work. "
            f"What do you need me to do?\n\n"
            f"Best,\n{settings.identity_display_name}"
        ),
        body_html=(
            f"<p>Hey zhixin!</p>"
            f"<p>I'm @{settings.identity_handle}, the Inkbox AI agent assigned to this session.</p>"
            f"<p>My email address is {settings.identity_email} and I'm set up and ready to work. "
            f"What do you need me to do?</p>"
            f"<p>Best,<br>{settings.identity_display_name}</p>"
        ),
    )
    print("Introduction email sent.")


def handle_research_leads(args: argparse.Namespace) -> None:
    leads = load_leads_from_csv(args.input)
    results = research_leads(leads)
    save_research_results(args.output, results)
    print(f"Saved research for {len(results)} lead(s) to {args.output}.")


def handle_draft_emails(args: argparse.Namespace) -> None:
    results = load_research_results(args.research_file)
    drafts = create_drafts(results, openai_settings=load_openai_settings_if_available())
    save_drafts_csv(args.output, drafts)
    print(f"Saved {len(drafts)} draft(s) to {args.output}. Review the 'approved' column before sending.")


def handle_send_approved(args: argparse.Namespace) -> None:
    settings = InkboxSettings.from_env()
    service = InkboxEmailService(settings)
    drafts = load_drafts_csv(args.drafts_file)
    updated_drafts = send_approved_drafts(
        service,
        drafts,
        review_email=settings.review_email,
        live_outreach_enabled=args.live or settings.live_outreach_enabled,
    )
    save_drafts_csv(args.drafts_file, updated_drafts)
    sent_count = sum(1 for draft in updated_drafts if draft.status == "sent")
    delivery_mode = "live company recipients" if args.live or settings.live_outreach_enabled else settings.review_email
    print(
        f"Draft processing complete. {sent_count} approved draft(s) are marked as sent in {args.drafts_file}. "
        f"Delivery target: {delivery_mode}."
    )


def handle_draft_company(args: argparse.Namespace) -> None:
    lead = Lead(
        company_name=args.company_name,
        website_url=args.website_url,
        contact_email=args.contact_email,
        contact_name=args.contact_name,
        careers_url=args.careers_url,
        notes=args.notes,
    )
    result = research_lead(lead)
    draft = create_draft_from_result(result, openai_settings=load_openai_settings_if_available())
    save_drafts_csv(args.output, [draft])
    print(render_company_draft_report(result, draft, args.output))


def load_openai_settings_if_available() -> OpenAISettings | None:
    try:
        return OpenAISettings.from_env()
    except ValueError:
        return None


def render_company_draft_report(result, draft, output_path: str) -> str:
    source_urls = "\n".join(f"- {url}" for url in result.source_urls) if result.source_urls else "- none"
    contact_email = draft.contact_email or "(not provided)"
    return (
        f"Saved 1 draft to {output_path}.\n\n"
        f"Company: {result.company_name}\n"
        f"Website: {result.website_url}\n"
        f"Contact: {draft.contact_name or '(not provided)'}\n"
        f"Discovered recipient email: {contact_email}\n"
        f"Default test recipient: {InkboxSettings.from_env().review_email}\n"
        f"Generation method: {draft.generation_method}\n\n"
        f"Research summary:\n{result.summary}\n\n"
        f"Hiring signal:\n{result.hiring_signal}\n\n"
        f"Personalization angle:\n{result.personalization_angle}\n\n"
        f"Source URLs:\n{source_urls}\n\n"
        f"Draft subject:\n{draft.subject}\n\n"
        f"Draft body:\n{draft.body_text}\n"
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    handler = args.handler
    handler(args)


if __name__ == "__main__":
    main()
