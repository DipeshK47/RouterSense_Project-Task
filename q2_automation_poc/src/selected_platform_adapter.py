from __future__ import annotations

import time
from typing import Any

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from .platform_adapter_base import PlatformAdapterBase
from .utils import append_log, clean_text, now_iso


class TalkieAdapter(PlatformAdapterBase):
    """
    Adapter for Talkie's public web chat pages.

    The selectors are intentionally documented and centralized because this UI can
    change and may need light maintenance after front-end updates.
    """

    def __init__(self, page, config, log_path: str):
        super().__init__(page, config, log_path)
        self.character_name = ""
        self.conversation_url = ""
        self.onboarding_seen = False
        self.login_not_required = False

    def open_platform(self) -> None:
        target = self.config.character_url or self.config.platform_url
        if not target:
            raise ValueError("A Talkie platform URL or character URL is required.")
        append_log(self.log_path, f"Opening platform URL: {target}")
        self.page.goto(target, wait_until="domcontentloaded", timeout=120000)
        self.page.wait_for_timeout(3000)
        self.conversation_url = self.page.url

    def login_if_needed(self, skip_login: bool = False) -> None:
        if skip_login:
            append_log(self.log_path, "Skipping login by request.")
            return

        # Public Talkie pages often allow guest interaction. If a login wall appears,
        # we stop rather than bypassing it.
        if self.page.get_by_text("Continue with Google").count() or self.page.get_by_text("Log in").count():
            raise RuntimeError(
                "Talkie presented a login requirement for this session. "
                "Provide a test account or choose a guest-accessible character page."
            )
        self.login_not_required = True

    def open_chat(self) -> None:
        self._dismiss_overlay_and_complete_onboarding()

        # Character name selectors may need adjustment if Talkie changes heading structure.
        heading = self.page.locator("h1").first
        if heading.count() and heading.is_visible():
            self.character_name = clean_text(heading.inner_text())
        elif self.page.locator(".ChatHeader_name__RDukb").count():
            self.character_name = clean_text(self.page.locator(".ChatHeader_name__RDukb").first.inner_text())
        else:
            self.character_name = "Talkie Character"

        if self.page.get_by_role("button", name="Chat Now").count():
            append_log(self.log_path, "Found Chat Now button; opening the live chat view.")
            self.page.get_by_role("button", name="Chat Now").first.click()
            self.page.wait_for_timeout(2500)

        self.conversation_url = self.page.url

    def _dismiss_overlay_and_complete_onboarding(self) -> None:
        body_text = clean_text(self.page.locator("body").inner_text()).lower()
        if "double-click on the blank area" in body_text:
            append_log(self.log_path, "Dismissing Talkie immersion overlay.")
            self.page.mouse.dblclick(720, 300)
            self.page.wait_for_timeout(1200)

        if "enter talkie now" not in body_text:
            body_text = clean_text(self.page.locator("body").inner_text()).lower()

        if "enter talkie now" in body_text:
            append_log(self.log_path, "Completing Talkie onboarding self-declaration flow.")
            self.onboarding_seen = True
            # These labels were confirmed during the live probe; adjust if Talkie changes onboarding text.
            for label in ["They/Them", "21-23", "🌈 Non-binary", "Enter Talkie Now!"]:
                loc = self.page.get_by_text(label, exact=True)
                if loc.count():
                    loc.first.click(force=True)
                    self.page.wait_for_timeout(700)
            self.page.wait_for_timeout(2500)

    def _message_input(self):
        candidates = [
            self.page.locator("textarea").first,
            self.page.locator("input[placeholder*='message' i]").first,
            self.page.locator("input[placeholder*='chat' i]").first,
            self.page.locator("textarea[placeholder]").first,
        ]
        for candidate in candidates:
            try:
                if candidate.count() and candidate.is_visible():
                    return candidate
            except Exception:
                continue
        raise RuntimeError("Could not find a visible chat input on the Talkie page.")

    def _send_button(self):
        candidates = [
            self.page.get_by_role("button", name="Send").first,
            self.page.locator("[alt*='send message to ai chat bot']").first,
            self.page.locator(".ChatBox_sendBtn__gW45g").first,
            self.page.locator("button:has(svg)").last,
            self.page.locator("[aria-label*='send' i]").first,
        ]
        for candidate in candidates:
            try:
                if candidate.count() and candidate.is_visible():
                    return candidate
            except Exception:
                continue
        return None

    def _bot_message_locator(self):
        # Talkie currently renders AI messages newest-first in the message container.
        return self.page.locator(".Message_aiMessage__RbW_p .Message_text___ukOO")

    def send_message(self, message: str) -> Any:
        input_box = self._message_input()
        bot_locator = self._bot_message_locator()
        previous_count = bot_locator.count()
        previous_top_text = ""
        if previous_count:
            try:
                previous_top_text = clean_text(bot_locator.first.inner_text())
            except Exception:
                previous_top_text = ""
        append_log(self.log_path, f"Sending message: {message}")
        input_box.focus()
        input_box.fill(message)
        input_box.press("Enter")
        return {
            "previous_count": previous_count,
            "previous_top_text": previous_top_text,
            "message_sent_at": time.time(),
        }

    def wait_for_response(self, previous_state: Any) -> None:
        previous_count = previous_state["previous_count"]
        previous_top_text = previous_state.get("previous_top_text", "")
        timeout_ms = int(self.config.response_timeout_seconds * 1000)
        start = time.time()
        last_count = previous_count
        last_top_text = previous_top_text
        stable_cycles = 0

        while (time.time() - start) * 1000 < timeout_ms:
            try:
                locator = self._bot_message_locator()
                current_count = locator.count()
                current_top_text = clean_text(locator.first.inner_text()) if current_count else ""
            except Exception:
                current_count = last_count
                current_top_text = last_top_text

            if current_count > previous_count:
                if current_count == last_count:
                    stable_cycles += 1
                else:
                    stable_cycles = 0
                last_count = current_count
                if stable_cycles >= 3:
                    return
            elif current_top_text and current_top_text != previous_top_text:
                if current_top_text == last_top_text:
                    stable_cycles += 1
                else:
                    stable_cycles = 0
                last_top_text = current_top_text
                if stable_cycles >= 3:
                    return
            self.page.wait_for_timeout(1500)

        raise PlaywrightTimeoutError("Timed out waiting for a new Talkie response.")

    def capture_response(self) -> str:
        locator = self._bot_message_locator()
        if not locator.count():
            return ""
        try:
            return clean_text(locator.first.inner_text())
        except Exception:
            return ""

    def run_conversation(self, messages: list[str]) -> list[dict]:
        transcript: list[dict] = []
        total_messages = len(messages)
        for index, message in enumerate(messages, start=1):
            sent_at = now_iso()
            start = time.time()
            status = "ok"
            error_message = ""
            response_text = ""
            response_at = ""
            append_log(
                self.log_path,
                f"Conversation step {index}/{total_messages}: preparing to send prompt.",
            )
            try:
                previous_state = self.send_message(message)
                self.wait_for_response(previous_state)
                response_text = self.capture_response()
                response_at = now_iso()
                self.page.wait_for_timeout(int(self.config.message_delay_seconds * 1000))
                append_log(
                    self.log_path,
                    f"Conversation step {index}/{total_messages}: received response in {round(time.time() - start, 2)}s. "
                    f"Preview: {clean_text(response_text)[:120]}",
                )
            except Exception as exc:
                status = "error"
                error_message = clean_text(exc)
                response_at = now_iso()
                append_log(self.log_path, f"Message {index} failed: {error_message}")

            transcript.append(
                {
                    "message_index": index,
                    "timestamp_sent": sent_at,
                    "input_message": message,
                    "timestamp_response": response_at,
                    "response_text": response_text,
                    "response_latency_seconds": round(time.time() - start, 2),
                    "platform_name": self.config.platform_name or "Talkie",
                    "platform_url": self.config.platform_url,
                    "character_name_or_id": self.character_name,
                    "conversation_url_or_identifier": self.conversation_url,
                    "automation_method": "Playwright UI automation",
                    "status": status,
                    "error_message": error_message,
                }
            )
        return transcript

    def cleanup(self) -> None:
        append_log(self.log_path, "Adapter cleanup complete.")
