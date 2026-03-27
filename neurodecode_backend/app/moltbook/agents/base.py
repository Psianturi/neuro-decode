"""
BaseAgent — minimal abstract class for all pipeline agents.

Each agent:
  - Has a name (for logging + audit trail)
  - Receives a typed input message
  - Returns a typed output message
  - Logs its work via the shared logger
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, name: str) -> None:
        self.name = name
        self._log = logging.getLogger(f"moltbook.agent.{name}")

    @abstractmethod
    async def run(self, message: Any) -> Any:
        """Process input message and return output message."""

    def log(self, msg: str, *args: Any) -> None:
        self._log.warning(f"[{self.name}] {msg}", *args)

    def warn(self, msg: str, *args: Any) -> None:
        self._log.warning(f"[{self.name}] WARN: {msg}", *args)
