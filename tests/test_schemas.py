import uuid
from datetime import datetime, timezone

from fan_experience.schemas.agent import AgentContext, PlanProposal
from fan_experience.schemas.common import PlanStatusEnum, ReservationStatusEnum
from fan_experience.schemas.plan import (
    FeedbackRequest,
    PlanResponse,
    PlanVersionResponse,
    RefineRequest,
    ShortlistOption,
)
from fan_experience.schemas.preference import PreferenceResponse
from fan_experience.schemas.purchase import PurchaseWebhook
from fan_experience.schemas.reservation import (
    ReservationConfirmRequest,
    ReservationPreviewRequest,
    ReservationPreviewResponse,
)


def test_purchase_webhook_validation():
    data = {
        "purchase_id": "ext-001",
        "user_id": str(uuid.uuid4()),
        "event_id": str(uuid.uuid4()),
        "ticket_count": 2,
        "purchased_at": datetime.now(timezone.utc).isoformat(),
        "hmac_signature": "abc123",
    }
    webhook = PurchaseWebhook(**data)
    assert webhook.ticket_count == 2


def test_shortlist_option():
    opt = ShortlistOption(
        candidate_id="rest-001",
        recommended=True,
        dining_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
        option_reasoning="Great Italian spot, 10-min walk to venue",
    )
    assert opt.recommended is True


def test_plan_proposal_schema():
    proposal = PlanProposal(
        shortlist=[
            ShortlistOption(
                candidate_id="rest-001",
                recommended=True,
                dining_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
                option_reasoning="Best match for preferences",
            ),
            ShortlistOption(
                candidate_id="rest-002",
                recommended=False,
                dining_time=datetime(2026, 7, 1, 17, 0, tzinfo=timezone.utc),
                option_reasoning="Budget-friendly alternative",
            ),
        ],
        plan_summary="Dinner at Bestia at 5:30pm, 10-min walk to Staples Center",
        conversation_history=[],
    )
    assert len(proposal.shortlist) == 2
    recommended = [o for o in proposal.shortlist if o.recommended]
    assert len(recommended) == 1


def test_refine_request():
    req = RefineRequest(
        message="Can you find something cheaper?",
        structured_preferences={"price_range": "low"},
    )
    assert req.message is not None
    assert req.structured_preferences["price_range"] == "low"


def test_refine_request_message_only():
    req = RefineRequest(message="Something with outdoor seating")
    assert req.structured_preferences is None


def test_reservation_preview_request():
    req = ReservationPreviewRequest(
        action="book",
        candidate_id="rest-001",
        dining_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
        party_size=2,
    )
    assert req.action == "book"


def test_feedback_request():
    req = FeedbackRequest(rating=4, comment="Great pick!")
    assert req.rating == 4
