from app.core.models import CamelCaseModel

class HealthCheckResponse(CamelCaseModel):
    status: str = "ok"
    last_backend_breaking_update: str 