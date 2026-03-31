import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as SyncSession

from fan_experience.db.models import UserPreference


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# managing learned preferences with simple confidence decay over time.
class PreferenceService:
    def __init__(self, session: SyncSession):
        self._session = session

    def update_preference(
        self,
        user_id: uuid.UUID,
        preference_type: str,
        value: dict,
        confidence: float,
    ) -> UserPreference:
        preference = self._session.execute(
            select(UserPreference).where(
                UserPreference.user_id == user_id,
                UserPreference.preference_type == preference_type,
            )
        ).scalar_one_or_none()

        if preference is None:
            preference = UserPreference(
                user_id=user_id,
                preference_type=preference_type,
                value_json=value,
                confidence=confidence,
            )
            self._session.add(preference)
        else:
            preference.value_json = value
            preference.confidence = confidence
            preference.updated_at = datetime.now(timezone.utc)

        self._session.commit()
        return preference

    def get_preferences(self, user_id: uuid.UUID) -> list[UserPreference]:
        return list(
            self._session.execute(
                select(UserPreference).where(UserPreference.user_id == user_id)
            ).scalars()
        )

    def apply_decay(
        self,
        user_id: uuid.UUID,
        decay_rate: float = 0.01,
        min_confidence: float = 0.1,
    ) -> None:
        now = datetime.now(timezone.utc)
        for preference in self.get_preferences(user_id):
            age_days = (now - _as_utc(preference.updated_at)).total_seconds() / 86400
            decayed_confidence = preference.confidence - (decay_rate * age_days)
            preference.confidence = max(min_confidence, decayed_confidence)

        self._session.commit()
