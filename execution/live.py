from __future__ import annotations

from data.schemas import Decision


class LiveExecutor:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    async def execute(self, decision: Decision) -> Decision:
        if not self.enabled:
            raise RuntimeError("Live trading is disabled. Set ENABLE_LIVE_TRADING=true explicitly.")
        raise NotImplementedError(
            "Live order placement scaffold is present but not wired. "
            "Use py-clob-client here after credentials, jurisdiction, and order policy are confirmed."
        )

