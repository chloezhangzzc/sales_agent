from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Lead:
    company_name: str
    website_url: str
    contact_email: str = ""
    contact_name: str = ""
    careers_url: str = ""
    notes: str = ""

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "Lead":
        company_name = row.get("company_name", "").strip()
        website_url = row.get("website_url", "").strip()
        contact_email = row.get("contact_email", "").strip()
        contact_name = row.get("contact_name", "").strip()
        careers_url = row.get("careers_url", "").strip()
        notes = row.get("notes", "").strip()

        if not company_name:
            raise ValueError("Missing required CSV field: company_name")
        if not website_url:
            raise ValueError(f"Missing website_url for company: {company_name}")

        return cls(
            company_name=company_name,
            website_url=website_url,
            contact_email=contact_email,
            contact_name=contact_name,
            careers_url=careers_url,
            notes=notes,
        )


def load_leads_from_csv(path: str | Path) -> list[Lead]:
    csv_path = Path(path)
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        return []

    return [Lead.from_row(row) for row in rows]
