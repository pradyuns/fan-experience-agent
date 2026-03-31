import uuid
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select

from fan_experience.api.deps import get_db, maybe_await
from fan_experience.db.models import UserPreference

router = APIRouter()


@router.get("/{user_id}/preferences")
async def get_preferences(user_id: uuid.UUID, db=Depends(get_db)) -> dict[str, Any]:
    preferences = list(
        (
            await maybe_await(
                db.execute(
                    select(UserPreference).where(UserPreference.user_id == user_id)
                )
            )
        ).scalars()
    )

    return {
        "user_id": str(user_id),
        "preferences": [
            {
                "id": str(preference.id),
                "preference_type": preference.preference_type,
                "value": preference.value_json,
                "confidence": preference.confidence,
                "updated_at": (
                    preference.updated_at.isoformat()
                    if preference.updated_at is not None
                    else None
                ),
            }
            for preference in preferences
        ],
    }
