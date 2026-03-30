import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from fan_experience.db.models import (
    AdaptationLog,
    AdaptationResult,
    Event,
    Notification,
    NotificationType,
    Plan,
    PlanStatus,
    PlanVersion,
    Purchase,
    Reservation,
    ReservationStatus,
    User,
    UserPreference,
)


# verifying users and purchases persist correctly.
def test_create_user_and_purchase(db_session):
    """All models can be instantiated and relationships work."""
    user = User(
        id=uuid.uuid4(),
        name="Test Fan",
        email="fan@test.com",
        timezone="US/Eastern",
    )
    event = Event(
        id=uuid.uuid4(),
        name="Lakers vs Celtics",
        venue_name="Staples Center",
        venue_address="1111 S Figueroa St",
        venue_lat=34.043,
        venue_lng=-118.267,
        event_time=datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc),
        doors_open=datetime(2026, 6, 15, 17, 30, tzinfo=timezone.utc),
        genre="basketball",
    )
    purchase = Purchase(
        id=uuid.uuid4(),
        user_id=user.id,
        event_id=event.id,
        purchase_id="ext-purchase-001",
        ticket_count=2,
        purchased_at=datetime.now(timezone.utc),
    )
    db_session.add_all([user, event, purchase])
    db_session.commit()

    result = db_session.execute(
        select(Purchase).where(Purchase.purchase_id == "ext-purchase-001")
    )
    row = result.scalar_one()
    assert row.ticket_count == 2
    assert row.user_id == user.id


# verifying plans can store versions, reservations, and notifications.
def test_plan_with_version_and_reservation(db_session):
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    user = User(id=user_id, name="Fan", email="f@t.com", timezone="UTC")
    event = Event(
        id=event_id,
        name="Concert",
        venue_name="V",
        venue_address="A",
        venue_lat=0.0,
        venue_lng=0.0,
        event_time=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc),
        doors_open=datetime(2026, 7, 1, 18, 30, tzinfo=timezone.utc),
        genre="music",
    )
    purchase = Purchase(
        id=uuid.uuid4(),
        user_id=user_id,
        event_id=event_id,
        purchase_id="ext-002",
        ticket_count=1,
        purchased_at=datetime.now(timezone.utc),
    )
    plan = Plan(
        id=uuid.uuid4(),
        purchase_id=purchase.id,
        user_id=user_id,
        event_id=event_id,
        status=PlanStatus.GENERATING,
    )
    version = PlanVersion(
        id=uuid.uuid4(),
        plan_id=plan.id,
        version_number=1,
        payload_json={"shortlist": []},
        confidence_score=0.85,
        confidence_breakdown_json={"freshness": 0.9, "margins": 0.8},
        trigger_reason="initial",
        agent_reasoning="First plan generation",
        conversation_history_json=[],
    )
    reservation = Reservation(
        id=uuid.uuid4(),
        plan_id=plan.id,
        restaurant_id="rest-001",
        restaurant_name="Bestia",
        status=ReservationStatus.PREVIEW_PENDING,
        party_size=2,
        reservation_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
        idempotency_key=str(uuid.uuid4()),
    )
    notification = Notification(
        id=uuid.uuid4(),
        plan_id=plan.id,
        type=NotificationType.PLAN_CREATED,
        message="Your dining plan is ready!",
    )
    db_session.add_all([user, event, purchase, plan, version, reservation, notification])
    db_session.commit()

    loaded_plan = db_session.execute(
        select(Plan).where(Plan.id == plan.id)
    ).scalar_one()
    assert loaded_plan.status == PlanStatus.GENERATING


# verifying preferences and adaptation logs can be queried after persistence.
def test_user_preference_and_adaptation_log(db_session):
    user_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    user = User(id=user_id, name="Fan", email="f@t.com", timezone="UTC")
    db_session.add(user)

    pref = UserPreference(
        id=uuid.uuid4(),
        user_id=user_id,
        preference_type="cuisine",
        value_json={"italian": 0.9, "japanese": 0.7},
        confidence=0.8,
    )
    event_id = uuid.uuid4()
    event = Event(
        id=event_id,
        name="Game",
        venue_name="V",
        venue_address="A",
        venue_lat=0.0,
        venue_lng=0.0,
        event_time=datetime(2026, 8, 1, 19, 0, tzinfo=timezone.utc),
        doors_open=datetime(2026, 8, 1, 17, 0, tzinfo=timezone.utc),
        genre="sports",
    )
    purchase = Purchase(
        id=uuid.uuid4(),
        user_id=user_id,
        event_id=event_id,
        purchase_id="ext-003",
        ticket_count=4,
        purchased_at=datetime.now(timezone.utc),
    )
    plan = Plan(
        id=plan_id,
        purchase_id=purchase.id,
        user_id=user_id,
        event_id=event_id,
        status=PlanStatus.ACTIVE,
    )
    log = AdaptationLog(
        id=uuid.uuid4(),
        plan_id=plan_id,
        tick_number=1,
        result=AdaptationResult.NO_CHANGE,
        trigger_details_json={"checked": ["weather", "traffic"]},
    )
    db_session.add_all([event, purchase, plan, pref, log])
    db_session.commit()

    loaded_pref = db_session.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    ).scalar_one()
    assert loaded_pref.confidence == 0.8

    loaded_log = db_session.execute(
        select(AdaptationLog).where(AdaptationLog.plan_id == plan_id)
    ).scalar_one()
    assert loaded_log.result == AdaptationResult.NO_CHANGE
