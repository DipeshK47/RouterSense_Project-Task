from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PlatformAdapterBase(ABC):
    def __init__(self, page, config, log_path: str):
        self.page = page
        self.config = config
        self.log_path = log_path

    @abstractmethod
    def open_platform(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def login_if_needed(self, skip_login: bool = False) -> None:
        raise NotImplementedError

    @abstractmethod
    def open_chat(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def send_message(self, message: str) -> Any:
        raise NotImplementedError

    @abstractmethod
    def wait_for_response(self, previous_state: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def capture_response(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def run_conversation(self, messages: list[str]) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self) -> None:
        raise NotImplementedError

