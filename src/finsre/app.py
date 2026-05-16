from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from finsre.config import get_settings
from finsre.connectors.registry import ConnectorRegistry, build_default_registry
from finsre.models import ConnectorDescriptor


class ConnectorResponse(BaseModel):
    name: str
    provider: str
    source_type: str
    status: str
    capabilities: list[str]
    details: dict[str, Any]


class QueryPreviewResponse(BaseModel):
    connector: str
    query: str


def _connector_response(descriptor: ConnectorDescriptor) -> ConnectorResponse:
    return ConnectorResponse(
        name=descriptor.name,
        provider=descriptor.provider.value,
        source_type=descriptor.source_type,
        status=descriptor.status.value,
        capabilities=list(descriptor.capabilities),
        details=descriptor.details,
    )


def create_app(registry: ConnectorRegistry | None = None) -> FastAPI:
    settings = get_settings()
    connector_registry = registry or build_default_registry(settings)
    app = FastAPI(title="FinSRE", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name, "environment": settings.environment}

    @app.get("/v1/connectors", response_model=list[ConnectorResponse])
    def list_connectors() -> list[ConnectorResponse]:
        return [_connector_response(connector.describe()) for connector in connector_registry.list()]

    @app.get("/v1/connectors/{name}/query-preview", response_model=QueryPreviewResponse)
    def preview_connector_query(name: str) -> QueryPreviewResponse:
        try:
            connector = connector_registry.get(name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        query = connector.preview_query()
        if not query:
            raise HTTPException(status_code=409, detail=f"Connector {name} is not configured for query preview.")
        return QueryPreviewResponse(connector=name, query=query)

    return app


def run() -> None:
    uvicorn.run("finsre.app:create_app", factory=True, host="0.0.0.0", port=8080)
