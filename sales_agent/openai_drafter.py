from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openai import OpenAI

from sales_agent.config import OpenAISettings
from sales_agent.research import ResearchResult


@dataclass(frozen=True)
class GeneratedEmail:
    subject: str
    body_text: str


SYSTEM_PROMPT = """You write concise, high-signal B2B sales outreach emails.

You are writing on behalf of Hirepilot, a company selling AI-native hiring software.

Hirepilot capabilities:
- candidate screening
- AI-generated online assessments
- AI voice Q&A / AI OA workflows
- evaluating how candidates perform with AI assistance
- founder interview support including interview question generation and interview evaluation summaries

Rules:
- Be specific to the target company.
- Do not invent facts not present in the provided research.
- Keep the email under 170 words.
- Sound like a thoughtful human sales rep, not a marketing blast.
- Include a clear but low-pressure call to action.
- Use only plain ASCII punctuation and quotes.
- End the email with exactly:
  Best,
  Chloe
- Return valid JSON only with keys: subject, body_text.
"""


def build_user_prompt(result: ResearchResult) -> str:
    contact_line = result.contact_name or "Unknown"
    return f"""
Target company: {result.company_name}
Target website: {result.website_url}
Contact name: {contact_line}
Contact email: {result.contact_email or "Unknown"}
Research summary: {result.summary}
Hiring signal: {result.hiring_signal}
Personalization angle: {result.personalization_angle}
Operator notes: {result.notes or "None"}
Source URLs: {", ".join(result.source_urls) or "None"}

Write one personalized cold outreach email for this lead.
"""


def sanitize_text(text: str) -> str:
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2011": "-",
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def enforce_signature(body_text: str, signature_name: str = "Chloe") -> str:
    normalized = sanitize_text(body_text)
    lines = [line.rstrip() for line in normalized.splitlines()]
    cleaned_lines: list[str] = []
    skip_signature_block = False

    for line in lines:
        lowered = line.strip().lower()
        if lowered in {"best,", "best", "thanks,", "thanks", "regards,", "regards", "sincerely,", "sincerely"}:
            skip_signature_block = True
            continue
        if skip_signature_block:
            if not lowered:
                continue
            continue
        cleaned_lines.append(line)

    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()

    cleaned = "\n".join(cleaned_lines).strip()
    if cleaned:
        cleaned = f"{cleaned}\n\nBest,\n{signature_name}"
    else:
        cleaned = f"Best,\n{signature_name}"
    return cleaned


def generate_email(result: ResearchResult, settings: OpenAISettings) -> GeneratedEmail:
    client = OpenAI(api_key=settings.api_key)
    response = client.responses.create(
        model=settings.model,
        input=[
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "input_text", "text": build_user_prompt(result)}]},
        ],
    )
    payload = json.loads(response.output_text)
    subject = sanitize_text(str(payload.get("subject", "")).strip())
    body_text = enforce_signature(str(payload.get("body_text", "")).strip(), signature_name="Chloe")
    if not subject or not body_text:
        raise ValueError("OpenAI response did not include both subject and body_text")
    return GeneratedEmail(subject=subject, body_text=body_text)
