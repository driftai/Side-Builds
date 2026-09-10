from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator


class RuntimeAdapter(ABC):
    @abstractmethod
    async def status(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def models(self) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def chat(self, payload: dict) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def chat_stream(self, payload: dict) -> AsyncIterator[bytes]:
        raise NotImplementedError
