from __future__ import annotations

from collections.abc import Sequence

from inkbox import Inkbox

from sales_agent.config import InkboxSettings


class InkboxEmailService:
    def __init__(self, settings: InkboxSettings) -> None:
        self._settings = settings

    def bootstrap_identity(self) -> None:
        with Inkbox(api_key=self._settings.api_key) as inkbox:
            self._get_or_create_identity(inkbox)

    def send_email(
        self,
        to: Sequence[str],
        subject: str,
        body_text: str,
        body_html: str | None = None,
    ) -> None:
        if not to:
            raise ValueError("At least one recipient is required")

        with Inkbox(api_key=self._settings.api_key) as inkbox:
            identity = self._get_or_create_identity(inkbox)
            payload = {
                "to": list(to),
                "subject": subject,
                "body_text": body_text,
            }
            if body_html:
                payload["body_html"] = body_html
            identity.send_email(**payload)

    def _get_or_create_identity(self, inkbox: Inkbox):
        try:
            return inkbox.get_identity(self._settings.identity_handle)
        except Exception as exc:
            if not self._looks_like_not_found(exc):
                raise

        return inkbox.create_identity(
            self._settings.identity_handle,
            display_name=self._settings.identity_display_name,
        )

    @staticmethod
    def _looks_like_not_found(exc: Exception) -> bool:
        message = str(exc).lower()
        not_found_markers = ("not found", "404", "does not exist", "unknown identity")
        return any(marker in message for marker in not_found_markers)
