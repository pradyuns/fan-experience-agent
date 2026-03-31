import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as SyncSession

from fan_experience.db.models import Reservation, ReservationStatus


# managing reservation preview and confirmation state transitions.
class ReservationService:
    def __init__(self, session: SyncSession):
        self._session = session

    def preview_booking(
        self,
        plan_id: uuid.UUID,
        restaurant_id: str,
        restaurant_name: str,
        party_size: int,
        reservation_time: datetime,
    ) -> Reservation:
        reservation = Reservation(
            id=uuid.uuid4(),
            plan_id=plan_id,
            restaurant_id=restaurant_id,
            restaurant_name=restaurant_name,
            status=ReservationStatus.PREVIEW_PENDING,
            party_size=party_size,
            reservation_time=reservation_time,
            idempotency_key=str(uuid.uuid4()),
            previewed_at=datetime.now(timezone.utc),
        )
        self._session.add(reservation)
        self._session.commit()
        return reservation

    def confirm_booking(self, idempotency_key: str) -> Reservation:
        reservation = self._get_by_key(idempotency_key)

        if reservation.status == ReservationStatus.CONFIRMED:
            return reservation

        if reservation.status != ReservationStatus.PREVIEW_PENDING:
            raise ValueError(f"Cannot confirm reservation in state {reservation.status}")

        reservation.status = ReservationStatus.CONFIRMED
        reservation.confirmed_at = datetime.now(timezone.utc)
        reservation.provider_confirmation_id = f"mock-confirm-{uuid.uuid4().hex[:8]}"
        self._session.commit()
        return reservation

    def preview_cancel(self, plan_id: uuid.UUID, restaurant_id: str) -> Reservation:
        reservation = self._session.execute(
            select(Reservation).where(
                Reservation.plan_id == plan_id,
                Reservation.restaurant_id == restaurant_id,
                Reservation.status == ReservationStatus.CONFIRMED,
            )
        ).scalar_one()

        reservation.status = ReservationStatus.CANCEL_PREVIEW_PENDING
        reservation.idempotency_key = str(uuid.uuid4())
        reservation.previewed_at = datetime.now(timezone.utc)
        self._session.commit()
        return reservation

    def confirm_cancel(self, idempotency_key: str) -> Reservation:
        reservation = self._get_by_key(idempotency_key)

        if reservation.status == ReservationStatus.CANCELLED:
            return reservation

        if reservation.status != ReservationStatus.CANCEL_PREVIEW_PENDING:
            raise ValueError(f"Cannot cancel reservation in state {reservation.status}")

        reservation.status = ReservationStatus.CANCELLED
        self._session.commit()
        return reservation

    # loading reservations by idempotency key for all confirm operations.
    def _get_by_key(self, idempotency_key: str) -> Reservation:
        reservation = self._session.execute(
            select(Reservation).where(Reservation.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if reservation is None:
            raise ValueError(f"Reservation with key {idempotency_key} not found")
        return reservation
