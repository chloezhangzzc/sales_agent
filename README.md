# AI Sales Outreach Agent

This project is a Python-based outbound sales agent that researches company websites, discovers hiring signals and public contact emails, generates personalized outreach drafts with OpenAI, and sends approved emails through Inkbox.

The current default mode is safe for testing:

- generated drafts can include a discovered company email such as `hello@linear.app`
- approved sends go to the review inbox `chloezzx@bu.edu` by default
- real customer delivery only happens when live sending is explicitly enabled

## Features

- Research a company website and try to detect a careers page
- Discover public contact emails from homepage, contact, about, team, and careers pages
- Generate personalized outreach emails with OpenAI
- Fall back to a local template if OpenAI is unavailable
- Print the research summary and draft directly in the terminal
- Save drafts to CSV for review and approval
- Route approved drafts to a safe review inbox by default
- Send real outreach only with an explicit `--live` flag

## Stack

- Python 3.11+
- [Inkbox](https://github.com/inkbox-ai/inkbox) for email delivery
- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses/create?lang=python) for personalized draft generation

## Setup

```bash
# Requires Python 3.11+. If your default is Python 3.9, use `python3.11 -m venv .venv` instead.
python -m venv .venv && source .venv/bin/activate
python -m pip install --upgrade pip
pip install inkbox openai
```

Create a local `.env` file:

```bash
cp .env.example .env
```

Expected variables:

```bash
INKBOX_API_KEY=ApiKey_your_key_here
INKBOX_IDENTITY_HANDLE=outreach-agent
INKBOX_IDENTITY_DISPLAY_NAME=Chloe
DEFAULT_SIGNATURE_NAME=Chloe
INKBOX_IDENTITY_EMAIL=hirepilot_outreach@inkboxmail.com
OUTREACH_REVIEW_EMAIL=chloezzx@bu.edu
ALLOW_LIVE_OUTREACH=false
OPENAI_API=sk_your_key_here
OPENAI_MODEL=gpt-5
OPENAI_BASE_URL=
OPENAI_PROXY_ENABLED=false
OPENAI_PROXY_URL=
```

- `DEFAULT_SIGNATURE_NAME` controls the signature used at the bottom of generated drafts.
- Leave `OPENAI_BASE_URL` empty to use the default OpenAI endpoint.
- Set `OPENAI_BASE_URL` to an OpenAI-compatible API endpoint such as `https://example.com/v1` when using another provider.
- Set `OPENAI_PROXY_ENABLED=true` and `OPENAI_PROXY_URL=http://127.0.0.1:7890` to route only AI requests through a proxy.

## Quick Start

### 1. Bootstrap the Inkbox identity

```bash
python main.py bootstrap
```

### 2. Generate one draft from a company name and website

```bash
python main.py draft-company \
  --company-name "Linear" \
  --website-url "https://linear.app" \
  --notes "Check if their hiring workflow could benefit from Hirepilot" \
  --output linear_draft.csv
```

This command:

1. researches the website
2. tries to detect a careers page
3. tries to discover a public contact email
4. sends the research into OpenAI
5. prints the research summary and draft in the terminal
6. writes one draft row to `linear_draft.csv`

### 3. Review the draft

Open `linear_draft.csv` and change:

```csv
approved=yes
```

### 4. Send the approved draft

Default safe mode sends to your review inbox:

```bash
python main.py send-approved --drafts-file linear_draft.csv
```

Live mode sends to the discovered company recipient:

```bash
python main.py send-approved --drafts-file linear_draft.csv --live
```

## Batch Workflow

Create a CSV such as:

```csv
company_name,website_url,contact_email,contact_name,careers_url,notes
Acme,https://acme.com,founder@acme.com,Alice,,Hiring engineers for product and infra
```

Only `company_name` and `website_url` are required.

If `contact_email` is blank, the research step will try to discover one from the website.

Run:

```bash
python main.py research-leads --input leads.csv --output research_results.json
python main.py draft-emails --research-file research_results.json --output outreach_drafts.csv
python main.py send-approved --drafts-file outreach_drafts.csv
```

## Safety Model

- `OUTREACH_REVIEW_EMAIL` controls where approved drafts go in test mode
- `ALLOW_LIVE_OUTREACH=false` keeps the project in safe review mode
- `--live` overrides that behavior for one send command
- `actual_recipient_email` in the CSV records where the email really went

## Commands

- `python main.py bootstrap`
- `python main.py send --to you@example.com --subject "Test" --body "Hello"`
- `python main.py send-intro`
- `python main.py research-leads --input leads.csv --output research_results.json`
- `python main.py draft-emails --research-file research_results.json --output outreach_drafts.csv`
- `python main.py send-approved --drafts-file outreach_drafts.csv`
- `python main.py send-approved --drafts-file outreach_drafts.csv --live`
- `python main.py draft-company --company-name "Linear" --website-url "https://linear.app" --output linear_draft.csv`

## Project Structure

- `main.py`: CLI entrypoint
- `sales_agent/config.py`: environment and runtime settings
- `sales_agent/email_service.py`: Inkbox email integration
- `sales_agent/leads.py`: CSV lead loading
- `sales_agent/research.py`: website research and email discovery
- `sales_agent/openai_drafter.py`: OpenAI draft generation and text cleanup
- `sales_agent/drafts.py`: draft creation, CSV persistence, and sending
- `tests/`: unit tests for config, research, generation, and sending behavior

## Testing

Run:

```bash
source .venv/bin/activate
python -m unittest discover -s tests
```
