from __future__ import annotations

from dataclasses import replace

from data.schemas import Decision


class PaperExecutor:
    async def execute(self, decision: Decision) -> Decision:
        return replace(decision, reason=f"paper_{decision.reason}")

