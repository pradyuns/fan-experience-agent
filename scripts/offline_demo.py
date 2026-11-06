"""Show the local candidate and timing checks without services or an API key."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from fan_experience.agent.guardrails import validate_against_event
from fan_experience.schemas.agent import PlanProposal
from fan_experience.schemas.plan import ShortlistOption
from fan_experience.tools.restaurants import search_restaurants


async def main():
    event = SimpleNamespace(
        venue_lat=34.043, venue_lng=-118.267,
        doors_open=datetime(2026, 7, 1, 18, 30, tzinfo=timezone.utc),
    )
    result = await search_restaurants(
        location=(event.venue_lat, event.venue_lng), radius_km=5,
        cuisine_types=None, party_size=2, date="2026-07-01",
        time_range=("00:00", "23:59"),
    )
    proposal = PlanProposal(
        shortlist=[
            ShortlistOption(
                candidate_id="rest-002", recommended=True,
                dining_time=datetime(2026, 7, 1, 17, 0, tzinfo=timezone.utc),
                option_reasoning="Example selection",
            ),
            ShortlistOption(
                candidate_id="rest-003", recommended=False,
                dining_time=datetime(2026, 7, 1, 17, 0, tzinfo=timezone.utc),
                option_reasoning="Example alternative",
            ),
        ],
        plan_summary="Example dinner before the event",
    )
    errors = await validate_against_event(proposal, event, 2)
    print("Offline demo: mock restaurants and estimated walking times; no reservation is made.")
    print("Candidates:", ", ".join(item["id"] + " (" + item["name"] + ")" for item in result.data))
    print("Example proposal:", ", ".join(option.candidate_id for option in proposal.shortlist))
    print("Validation:", "; ".join(errors) if errors else "passed")


if __name__ == "__main__":
    asyncio.run(main())
