from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ToolResult:
    """Base result for all agent tools. Includes source and freshness metadata."""

    data: Any
    source: str
    freshness_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
