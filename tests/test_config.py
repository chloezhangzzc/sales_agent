from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sales_agent.config import InkboxSettings, OpenAISettings, get_default_signature_name


class InkboxSettingsTests(unittest.TestCase):
    def test_requires_api_key(self) -> None:
        with patch("sales_agent.config.load_local_env"):
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "INKBOX_API_KEY"):
                    InkboxSettings.from_env()

    def test_loads_defaults(self) -> None:
        with patch("sales_agent.config.load_local_env"):
            with patch.dict(os.environ, {"INKBOX_API_KEY": "test-key"}, clear=True):
                settings = InkboxSettings.from_env()

        self.assertEqual(settings.api_key, "test-key")
        self.assertEqual(settings.identity_handle, "outreach-agent")
        self.assertEqual(settings.identity_display_name, "Chloe")
        self.assertEqual(settings.identity_email, "hirepilot_outreach@inkboxmail.com")
        self.assertEqual(settings.review_email, "chloezzx@bu.edu")
        self.assertFalse(settings.live_outreach_enabled)

    def test_loads_api_key_from_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text("INKBOX_API_KEY=dotenv-key\n", encoding="utf-8")

            previous_cwd = Path.cwd()
            os.chdir(tmpdir)
            try:
                with patch.dict(os.environ, {}, clear=True):
                    settings = InkboxSettings.from_env()
            finally:
                os.chdir(previous_cwd)

        self.assertEqual(settings.api_key, "dotenv-key")


class OpenAISettingsTests(unittest.TestCase):
    def test_requires_openai_key(self) -> None:
        with patch("sales_agent.config.load_local_env"):
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(ValueError, "OPENAI_API"):
                    OpenAISettings.from_env()

    def test_loads_openai_defaults(self) -> None:
        with patch("sales_agent.config.load_local_env"):
            with patch.dict(os.environ, {"OPENAI_API": "sk-test"}, clear=True):
                settings = OpenAISettings.from_env()

        self.assertEqual(settings.api_key, "sk-test")
        self.assertEqual(settings.model, "gpt-5")
        self.assertIsNone(settings.base_url)
        self.assertFalse(settings.proxy_enabled)
        self.assertIsNone(settings.proxy_url)

    def test_loads_openai_optional_base_url_and_proxy(self) -> None:
        with patch("sales_agent.config.load_local_env"):
            with patch.dict(
                os.environ,
                {
                    "OPENAI_API": "sk-test",
                    "OPENAI_MODEL": "gpt-4.1-mini",
                    "OPENAI_BASE_URL": "https://example.com/v1",
                    "OPENAI_PROXY_ENABLED": "true",
                    "OPENAI_PROXY_URL": "http://127.0.0.1:7890",
                },
                clear=True,
            ):
                settings = OpenAISettings.from_env()

        self.assertEqual(settings.model, "gpt-4.1-mini")
        self.assertEqual(settings.base_url, "https://example.com/v1")
        self.assertTrue(settings.proxy_enabled)
        self.assertEqual(settings.proxy_url, "http://127.0.0.1:7890")

    def test_requires_proxy_url_when_proxy_is_enabled(self) -> None:
        with patch("sales_agent.config.load_local_env"):
            with patch.dict(
                os.environ,
                {
                    "OPENAI_API": "sk-test",
                    "OPENAI_PROXY_ENABLED": "true",
                },
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "OPENAI_PROXY_URL"):
                    OpenAISettings.from_env()


class SignatureNameTests(unittest.TestCase):
    def test_uses_default_signature_name_from_env(self) -> None:
        with patch("sales_agent.config.load_local_env"):
            with patch.dict(
                os.environ,
                {
                    "DEFAULT_SIGNATURE_NAME": "Lycself",
                    "INKBOX_IDENTITY_DISPLAY_NAME": "Ignored Name",
                },
                clear=True,
            ):
                signature_name = get_default_signature_name()

        self.assertEqual(signature_name, "Lycself")

    def test_falls_back_to_identity_display_name(self) -> None:
        with patch("sales_agent.config.load_local_env"):
            with patch.dict(
                os.environ,
                {
                    "INKBOX_IDENTITY_DISPLAY_NAME": "Lycself",
                },
                clear=True,
            ):
                signature_name = get_default_signature_name()

        self.assertEqual(signature_name, "Lycself")


if __name__ == "__main__":
    unittest.main()
