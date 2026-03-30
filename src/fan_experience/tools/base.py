from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# standard wrapper for all tool responses
@dataclass
class ToolResult:
    data: Any
    source: str
    freshness_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
