import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from fan_experience.db.models import User, UserPreference
from fan_experience.services.preference_service import PreferenceService


def _seed_user(session) -> uuid.UUID:
    user_id = uuid.uuid4()
    session.add(User(id=user_id, name="Fan", email="f@t.com", timezone="UTC"))
    session.commit()
    return user_id


def test_update_preference_creates_new(db_session):
    user_id = _seed_user(db_session)
    service = PreferenceService(db_session)

    service.update_preference(user_id, "cuisine", {"italian": 0.9}, confidence=0.8)

    prefs = db_session.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    ).scalars()

    loaded = list(prefs)
    assert len(loaded) == 1
    assert loaded[0].preference_type == "cuisine"
    assert loaded[0].value_json == {"italian": 0.9}
    assert loaded[0].confidence == 0.8


def test_update_preference_upserts(db_session):
    user_id = _seed_user(db_session)
    service = PreferenceService(db_session)

    service.update_preference(user_id, "cuisine", {"italian": 0.9}, confidence=0.8)
    service.update_preference(
        user_id,
        "cuisine",
        {"italian": 0.95, "japanese": 0.7},
        confidence=0.9,
    )

    prefs = db_session.execute(
        select(UserPreference).where(
            UserPreference.user_id == user_id,
            UserPreference.preference_type == "cuisine",
        )
    ).scalars()

    loaded = list(prefs)
    assert len(loaded) == 1
    assert loaded[0].value_json["japanese"] == 0.7
    assert loaded[0].confidence == 0.9


def test_get_all_preferences(db_session):
    user_id = _seed_user(db_session)
    service = PreferenceService(db_session)

    service.update_preference(user_id, "cuisine", {"italian": 0.9}, confidence=0.8)
    service.update_preference(user_id, "price", {"range": "medium"}, confidence=0.7)

    preference_types = {
        preference.preference_type for preference in service.get_preferences(user_id)
    }

    assert preference_types == {"cuisine", "price"}


def test_decay_confidence(db_session):
    user_id = _seed_user(db_session)
    service = PreferenceService(db_session)

    service.update_preference(user_id, "cuisine", {"italian": 0.9}, confidence=1.0)

    preference = db_session.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    ).scalar_one()
    preference.updated_at = datetime.now(timezone.utc) - timedelta(days=90)
    db_session.commit()

    service.apply_decay(user_id, decay_rate=0.01, min_confidence=0.1)

    reloaded = db_session.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    ).scalar_one()
    assert reloaded.confidence < 1.0
    assert reloaded.confidence >= 0.1
