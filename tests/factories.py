import uuid
from datetime import datetime, timedelta, timezone

import factory

from fan_experience.db.models import Event, Plan, PlanStatus, Purchase, User


class UserFactory(factory.Factory):
    class Meta:
        model = User

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Faker("name")
    email = factory.Faker("email")
    timezone = "US/Eastern"


class EventFactory(factory.Factory):
    class Meta:
        model = Event

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Faker("catch_phrase")
    venue_name = factory.Faker("company")
    venue_address = factory.Faker("address")
    venue_lat = 34.043
    venue_lng = -118.267
    event_time = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) + timedelta(days=7)
    )
    doors_open = factory.LazyFunction(
        lambda: datetime.now(timezone.utc) + timedelta(days=7, hours=-1.5)
    )
    genre = "music"


class PurchaseFactory(factory.Factory):
    class Meta:
        model = Purchase

    id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    event_id = factory.LazyFunction(uuid.uuid4)
    purchase_id = factory.LazyFunction(lambda: f"ext-{uuid.uuid4().hex[:8]}")
    ticket_count = 2
    purchased_at = factory.LazyFunction(lambda: datetime.now(timezone.utc))


class PlanFactory(factory.Factory):
    class Meta:
        model = Plan

    id = factory.LazyFunction(uuid.uuid4)
    purchase_id = factory.LazyFunction(uuid.uuid4)
    user_id = factory.LazyFunction(uuid.uuid4)
    event_id = factory.LazyFunction(uuid.uuid4)
    status = PlanStatus.GENERATING
