from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="Fan Experience Agent", version="0.1.0")

    from fan_experience.api.plans import router as plans_router
    from fan_experience.api.reservations import router as reservations_router
    from fan_experience.api.users import router as users_router
    from fan_experience.api.webhooks import router as webhooks_router

    app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])
    app.include_router(plans_router, prefix="/plans", tags=["plans"])
    app.include_router(reservations_router, tags=["reservations"])
    app.include_router(users_router, prefix="/users", tags=["users"])

    return app
