from opentelemetry.sdk.resources import Resource

from fan_experience.config import Settings


def otel_resource(app_settings: Settings) -> Resource:
    return Resource.create(
        {
            "service.name": app_settings.telemetry_service_name,
            "deployment.environment": app_settings.telemetry_env,
        }
    )


def signal_endpoint(base_endpoint: str, signal_name: str) -> str:
    trimmed = base_endpoint.rstrip("/")
    if trimmed.endswith(f"/v1/{signal_name}"):
        return trimmed
    return f"{trimmed}/v1/{signal_name}"
