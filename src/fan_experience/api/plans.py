import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from fan_experience.api.deps import get_db, maybe_await
from fan_experience.db.models import Plan, PlanVersion
from fan_experience.schemas.plan import FeedbackRequest, RefineRequest

router = APIRouter()


@router.get("/{plan_id}")
async def get_plan(plan_id: uuid.UUID, db=Depends(get_db)) -> dict[str, Any]:
    plan = (
        await maybe_await(db.execute(select(Plan).where(Plan.id == plan_id)))
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    versions = list(
        (
            await maybe_await(
                db.execute(
                    select(PlanVersion)
                    .where(PlanVersion.plan_id == plan_id)
                    .order_by(PlanVersion.version_number.desc())
                )
            )
        ).scalars()
    )

    version_data = [
        {
            "id": str(version.id),
            "version_number": version.version_number,
            "shortlist": version.payload_json.get("shortlist", []),
            "plan_summary": version.payload_json.get("plan_summary", ""),
            "confidence_score": version.confidence_score,
            "confidence_breakdown": version.confidence_breakdown_json,
            "trigger_reason": version.trigger_reason,
            "agent_reasoning": version.agent_reasoning,
            "created_at": version.created_at.isoformat() if version.created_at else None,
        }
        for version in versions
    ]

    return {
        "id": str(plan.id),
        "status": plan.status.value,
        "current_version": version_data[0] if version_data else None,
        "versions": version_data,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
    }


@router.post("/{plan_id}/refine")
async def refine_plan(
    plan_id: uuid.UUID,
    body: RefineRequest,
    db=Depends(get_db),
) -> dict[str, str]:
    plan = (
        await maybe_await(db.execute(select(Plan).where(Plan.id == plan_id)))
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    return {"status": "refine_queued", "plan_id": str(plan_id)}


@router.post("/{plan_id}/feedback")
async def submit_feedback(
    plan_id: uuid.UUID,
    body: FeedbackRequest,
    db=Depends(get_db),
) -> dict[str, str]:
    plan = (
        await maybe_await(db.execute(select(Plan).where(Plan.id == plan_id)))
    ).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    return {"status": "feedback_received", "plan_id": str(plan_id)}
