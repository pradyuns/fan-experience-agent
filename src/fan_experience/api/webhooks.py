import hashlib
import hmac
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select

from fan_experience.api.deps import get_db, maybe_await
from fan_experience.config import settings
from fan_experience.db.models import Plan, PlanStatus, Purchase
from fan_experience.tasks.plan_generation import run_plan_generation

router = APIRouter()


def _verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


dispatch_plan_generation = run_plan_generation


@router.post("/purchase", status_code=201)
async def receive_purchase(request: Request, db=Depends(get_db)) -> dict[str, str | None]:
    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    if not _verify_hmac(body, signature, settings.webhook_hmac_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = json.loads(body)

    existing_purchase = (
        await maybe_await(
            db.execute(select(Purchase).where(Purchase.purchase_id == data["purchase_id"]))
        )
    ).scalar_one_or_none()
    if existing_purchase is not None:
        existing_plan = (
            await maybe_await(
                db.execute(select(Plan).where(Plan.purchase_id == existing_purchase.id))
            )
        ).scalar_one_or_none()
        return {
            "plan_id": str(existing_plan.id) if existing_plan is not None else None,
            "status": "already_processed",
        }

    purchase = Purchase(
        id=uuid.uuid4(),
        user_id=uuid.UUID(data["user_id"]),
        event_id=uuid.UUID(data["event_id"]),
        purchase_id=data["purchase_id"],
        ticket_count=data["ticket_count"],
        purchased_at=datetime.fromisoformat(data["purchased_at"]),
    )
    db.add(purchase)
    await maybe_await(db.flush())

    plan = Plan(
        id=uuid.uuid4(),
        purchase_id=purchase.id,
        user_id=purchase.user_id,
        event_id=purchase.event_id,
        status=PlanStatus.GENERATING,
    )
    db.add(plan)
    await maybe_await(db.commit())

    dispatch_plan_generation.delay(str(plan.id))
    return {"plan_id": str(plan.id), "status": "generating"}
