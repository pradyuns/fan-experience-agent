import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from opentelemetry import trace
from sqlalchemy import select

from fan_experience.api.deps import get_db, maybe_await
from fan_experience.config import settings
from fan_experience.db.models import Plan, PlanStatus, Purchase
from fan_experience.tasks.plan_generation import run_plan_generation
from fan_experience.telemetry.context import bind_context
from fan_experience.telemetry.logging import emit_event, get_logger
from fan_experience.telemetry.metrics import record_webhook_event
from fan_experience.telemetry.tracing import inject_context, set_span_attributes

router = APIRouter()
logger = get_logger(__name__)


def _verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


dispatch_plan_generation = run_plan_generation


@router.post("/purchase", status_code=201)
async def receive_purchase(request: Request, db=Depends(get_db)) -> dict[str, str | None]:
    body = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")

    if not _verify_hmac(body, signature, settings.webhook_hmac_secret):
        record_webhook_event("invalid_signature")
        emit_event(
            logger,
            "webhook.purchase.invalid_signature",
            level=logging.WARNING,
            status="invalid_signature",
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        data = json.loads(body)
        current_span = trace.get_current_span()
        set_span_attributes(
            current_span,
            **{
                "purchase.external_id": data.get("purchase_id"),
                "event.id": data.get("event_id"),
            },
        )

        with bind_context(
            purchase_id=data.get("purchase_id"),
            user_id=data.get("user_id"),
        ):
            existing_purchase = (
                await maybe_await(
                    db.execute(
                        select(Purchase).where(Purchase.purchase_id == data["purchase_id"])
                    )
                )
            ).scalar_one_or_none()
            if existing_purchase is not None:
                existing_plan = (
                    await maybe_await(
                        db.execute(select(Plan).where(Plan.purchase_id == existing_purchase.id))
                    )
                ).scalar_one_or_none()
                plan_id = str(existing_plan.id) if existing_plan is not None else None
                set_span_attributes(current_span, **{"plan.id": plan_id})
                record_webhook_event("duplicate")
                with bind_context(plan_id=plan_id):
                    emit_event(
                        logger,
                        "webhook.purchase.duplicate",
                        status="duplicate",
                        event_id=data["event_id"],
                    )
                return {
                    "plan_id": plan_id,
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

            set_span_attributes(
                current_span,
                **{
                    "plan.id": str(plan.id),
                    "purchase.external_id": purchase.purchase_id,
                    "event.id": str(purchase.event_id),
                },
            )
            record_webhook_event("accepted")
            with bind_context(
                plan_id=str(plan.id),
                purchase_id=purchase.purchase_id,
                user_id=str(purchase.user_id),
            ):
                emit_event(
                    logger,
                    "webhook.purchase.received",
                    status="accepted",
                    event_id=str(purchase.event_id),
                )
                dispatch_plan_generation.apply_async(
                    args=[str(plan.id)],
                    headers=inject_context(),
                )

            return {"plan_id": str(plan.id), "status": "generating"}
    except HTTPException:
        raise
    except Exception as exc:
        record_webhook_event("error")
        emit_event(
            logger,
            "webhook.purchase.error",
            level=logging.ERROR,
            status="error",
            error_type=type(exc).__name__,
        )
        raise
