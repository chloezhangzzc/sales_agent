from __future__ import annotations

import json
import re
from dataclasses import dataclass

try:
    from openai import DefaultHttpxClient, OpenAI
except ImportError:  # pragma: no cover - exercised in environments without optional deps installed.
    DefaultHttpxClient = None
    OpenAI = None

from sales_agent.config import OpenAISettings, get_default_signature_name
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
- Return valid JSON only with keys: subject, body_text.
"""


def build_user_prompt(result: ResearchResult) -> str:
    contact_line = result.contact_name or "Unknown"
    signature_name = get_default_signature_name()
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
End the email with exactly:
Best,
{signature_name}
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


def build_openai_client(
    settings: OpenAISettings,
    client_factory=None,
    http_client_factory=None,
):
    client_factory = client_factory or OpenAI
    if client_factory is None:
        raise ImportError("The openai package is required to generate drafts")

    client_kwargs = {"api_key": settings.api_key}
    if settings.base_url:
        client_kwargs["base_url"] = settings.base_url

    if settings.proxy_enabled:
        http_client_factory = http_client_factory or DefaultHttpxClient
        if http_client_factory is None:
            raise ImportError("The openai package is required to configure an HTTP proxy")
        client_kwargs["http_client"] = http_client_factory(proxy=settings.proxy_url)

    return client_factory(**client_kwargs)


def _extract_message_text(content) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text)
                continue
            if isinstance(text, dict) and isinstance(text.get("value"), str):
                parts.append(text["value"])
        return "\n".join(part for part in parts if part).strip()

    return ""


def _parse_payload(raw_text: str) -> dict:
    candidate = raw_text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start != -1 and end != -1 and start < end:
            return json.loads(candidate[start : end + 1])
        raise ValueError("OpenAI response was not valid JSON") from exc


def generate_email(result: ResearchResult, settings: OpenAISettings) -> GeneratedEmail:
    signature_name = get_default_signature_name()
    client = build_openai_client(settings)
    try:
        response = client.chat.completions.create(
            model=settings.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(result)},
            ],
        )
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()

    message = response.choices[0].message
    payload = _parse_payload(_extract_message_text(getattr(message, "content", "")))
    subject = sanitize_text(str(payload.get("subject", "")).strip())
    body_text = enforce_signature(str(payload.get("body_text", "")).strip(), signature_name=signature_name)
    if not subject or not body_text:
        raise ValueError("OpenAI response did not include both subject and body_text")
    return GeneratedEmail(subject=subject, body_text=body_text)
