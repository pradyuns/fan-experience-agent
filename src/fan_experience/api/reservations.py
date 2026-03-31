import uuid
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from fan_experience.api.deps import get_db, maybe_await
from fan_experience.db.models import Reservation, ReservationStatus
from fan_experience.schemas.reservation import (
    ReservationConfirmRequest,
    ReservationPreviewRequest,
)
from fan_experience.telemetry.context import bind_context
from fan_experience.telemetry.logging import emit_event, get_logger
from fan_experience.telemetry.metrics import record_reservation_action

router = APIRouter()
logger = get_logger(__name__)


@router.post("/plans/{plan_id}/reservations/preview")
async def preview_reservation(
    plan_id: uuid.UUID,
    body: ReservationPreviewRequest,
    db=Depends(get_db),
) -> dict[str, Any]:
    with bind_context(plan_id=str(plan_id)):
        reservation = Reservation(
            plan_id=plan_id,
            restaurant_id=body.candidate_id,
            restaurant_name=body.candidate_id,
            status=ReservationStatus.PREVIEW_PENDING,
            party_size=body.party_size,
            reservation_time=body.dining_time,
            idempotency_key=str(uuid.uuid4()),
            previewed_at=datetime.now(timezone.utc),
        )
        db.add(reservation)
        await maybe_await(db.commit())
        record_reservation_action(action="preview", result="success")
        emit_event(
            logger,
            "reservation.preview.created",
            action="preview",
            status="success",
        )

        return {
            "reservation_id": str(reservation.id),
            "status": reservation.status.value,
            "restaurant_id": reservation.restaurant_id,
            "party_size": reservation.party_size,
            "reservation_time": reservation.reservation_time.isoformat(),
            "idempotency_key": reservation.idempotency_key,
        }


@router.post("/plans/{plan_id}/reservations/confirm")
async def confirm_reservation(
    plan_id: uuid.UUID,
    body: ReservationConfirmRequest,
    db=Depends(get_db),
) -> dict[str, Any]:
    with bind_context(plan_id=str(plan_id)):
        reservation = (
            await maybe_await(
                db.execute(
                    select(Reservation).where(
                        Reservation.idempotency_key == body.idempotency_key
                    )
                )
            )
        ).scalar_one_or_none()
        if reservation is None:
            record_reservation_action(action="confirm", result="not_found")
            emit_event(
                logger,
                "reservation.confirm.rejected",
                level=logging.WARNING,
                action="confirm",
                status="not_found",
                error_type="ReservationNotFound",
            )
            raise HTTPException(status_code=400, detail="Reservation not found")

        if reservation.status == ReservationStatus.CONFIRMED:
            record_reservation_action(action="confirm", result="success")
            emit_event(
                logger,
                "reservation.confirmed",
                action="confirm",
                status="success",
            )
            return _reservation_response(reservation)

        if reservation.status != ReservationStatus.PREVIEW_PENDING:
            record_reservation_action(action="confirm", result="invalid_state")
            emit_event(
                logger,
                "reservation.confirm.rejected",
                level=logging.WARNING,
                action="confirm",
                status="invalid_state",
                error_type="InvalidReservationState",
            )
            raise HTTPException(
                status_code=400,
                detail=f"Cannot confirm reservation in state {reservation.status}",
            )

        reservation.status = ReservationStatus.CONFIRMED
        reservation.provider_confirmation_id = f"mock-confirm-{uuid.uuid4().hex[:8]}"
        reservation.confirmed_at = datetime.now(timezone.utc)
        await maybe_await(db.commit())
        record_reservation_action(action="confirm", result="success")
        emit_event(
            logger,
            "reservation.confirmed",
            action="confirm",
            status="success",
        )

        return _reservation_response(reservation)


def _reservation_response(reservation: Reservation) -> dict[str, Any]:
    return {
        "reservation_id": str(reservation.id),
        "status": reservation.status.value,
        "provider_confirmation_id": reservation.provider_confirmation_id,
        "confirmed_at": (
            reservation.confirmed_at.isoformat()
            if reservation.confirmed_at is not None
            else None
        ),
    }
