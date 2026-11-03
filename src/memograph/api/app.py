"""FastAPI application factory for Memograph."""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

try:
    from fastapi import (
        APIRouter,
        Depends,
        FastAPI,
        Header,
        HTTPException,
        Query,
        Request,
        WebSocket,
        WebSocketDisconnect,
    )
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
except ImportError as exc:  # pragma: no cover - depends on optional extra
    raise RuntimeError("Install the 'memograph[api]' extra to use the REST API.") from exc

from .. import MemoGraph, __version__
from ..errors import ResourceLimitError, ValidationError
from ..models import TopicFile
from .audit import audit
from .auth import APIKeyAuth
from .events import EventBroker, make_event
from .middleware import RequestIDMiddleware, RequestSizeLimitMiddleware
from .rate_limit import RateLimiter
from .schemas import (
    ContextRequest,
    ContextResponse,
    DreamRequest,
    ForgetRequest,
    GrepRequest,
    HealthResponse,
    IndexResponse,
    PruneResponse,
    RememberRequest,
    UpdateRequest,
    WriteResultResponse,
)
from .settings import APISettings


def create_app(settings: APISettings | None = None) -> FastAPI:
    """Build an authenticated, explicitly single-user Memograph API application.

    Args:
        settings: Explicit settings. When omitted, values are read from
            ``MEMOGRAPH_*`` environment variables and ``.env``.

    Raises:
        RuntimeError: If no API key is configured or multi-user mode is requested.

    Returns:
        A configured FastAPI app. All memory routes and the WebSocket require
        the API key; only ``/health`` and ``/openapi.json`` are public.
    """
    settings = settings or APISettings()
    if not settings.single_user_mode:
        raise RuntimeError(
            "Single-user mode is required; per-client authorization is not implemented. "
            "MEMOGRAPH_API_SINGLE_USER_MODE must remain true."
        )
    api_key = settings.api_key.get_secret_value()
    if not api_key:
        raise RuntimeError(
            "MEMOGRAPH_API_KEY is required; set it or pass APISettings(api_key=...)."
        )

    auth = APIKeyAuth(api_key)
    limiter = RateLimiter(settings.rate_limit_per_minute)
    dream_limiter = RateLimiter(settings.dream_rate_limit_per_minute)
    events = EventBroker(max_subscribers=settings.max_websocket_connections)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        manager = MemoGraph(config=settings.to_memograph_config())
        await manager.initialize()
        app.state.manager = manager
        try:
            yield
        finally:
            app.state.manager = None
            await manager.close()
            await events.close()

    app = FastAPI(
        title="Memograph API",
        version=__version__,
        description="Authenticated memory service for AI agents.",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.add_middleware(RequestSizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(RequestIDMiddleware)
    app.state.settings = settings
    app.state.auth = auth
    app.state.rate_limiter = limiter
    app.state.dream_rate_limiter = dream_limiter
    app.state.events = events
    app.state.manager = None

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        audit(
            "validation.failure",
            request_id=str(getattr(request.state, "request_id", "unknown")),
            path=request.url.path,
            error=str(exc),
        )
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ResourceLimitError)
    async def resource_limit_handler(request: Request, exc: ResourceLimitError) -> JSONResponse:
        audit(
            "resource_limit.exceeded",
            request_id=str(getattr(request.state, "request_id", "unknown")),
            path=request.url.path,
            error=str(exc),
        )
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["X-API-Key", "Authorization", "Content-Type"],
        )

    def request_id(request: Request) -> str:
        return str(getattr(request.state, "request_id", "unknown"))

    async def require_auth(
        request: Request,
        x_api_key: str | None = Header(default=None, alias="X-API-Key"),
        authorization: str | None = Header(default=None, alias="Authorization"),
    ) -> str:
        fingerprint = auth.verify(x_api_key, authorization)
        if fingerprint is None:
            audit(
                "auth.failure",
                request_id=request_id(request),
                path=request.url.path,
                client=request.client.host if request.client else None,
            )
            raise HTTPException(
                status_code=401,
                detail="Invalid or missing API key",
                headers={"WWW-Authenticate": "Bearer"},
            )
        request.state.client_id = fingerprint
        return fingerprint

    async def enforce_rate_limit(
        request: Request,
        client_id: str = Depends(require_auth),
    ) -> None:
        if not await limiter.acquire(client_id):
            audit(
                "rate_limit.exceeded",
                request_id=request_id(request),
                client_id=client_id,
                path=request.url.path,
            )
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": "60"},
            )

    async def enforce_dream_rate_limit(
        request: Request,
        client_id: str = Depends(require_auth),
    ) -> None:
        if not await dream_limiter.acquire(client_id):
            audit(
                "dream.rate_limited",
                request_id=request_id(request),
                client_id=client_id,
                path=request.url.path,
            )
            raise HTTPException(
                status_code=429,
                detail="Consolidation rate limit exceeded",
                headers={"Retry-After": "60"},
            )

    def get_manager(request: Request) -> MemoGraph:
        manager: MemoGraph | None = getattr(request.app.state, "manager", None)
        if manager is None:
            raise HTTPException(status_code=503, detail="Memograph is not initialized")
        return manager

    def publish(request: Request, event_type: str, **payload: Any) -> None:
        broker: EventBroker = request.app.state.events
        broker.publish(make_event(event_type, **payload))
        audit(
            event_type,
            request_id=request_id(request),
            client_id=getattr(request.state, "client_id", "unknown"),
            **payload,
        )

    router = APIRouter(dependencies=[Depends(enforce_rate_limit)])

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        """Unauthenticated liveness probe."""
        return HealthResponse(version=__version__)

    @router.get("/status", response_model=dict[str, Any], tags=["memory"])
    async def status(request: Request) -> dict[str, Any]:
        """Return provider, topic, index, consolidation, and usage status."""
        return await get_manager(request).status()

    @router.post("/remember", response_model=WriteResultResponse, tags=["memory"])
    async def remember(payload: RememberRequest, request: Request) -> WriteResultResponse:
        """Store one fact and emit a ``memory.remembered`` event on success."""
        result = await get_manager(request).remember(
            payload.topic_id,
            payload.content,
            payload.source,
            confidence=payload.confidence or "observed",
            tags=payload.tags,
            verification_hint=payload.verification_hint,
        )
        if result.success and result.fact is not None:
            publish(
                request,
                "memory.remembered",
                topic_id=payload.topic_id,
                fact_id=result.fact.fact_id,
            )
        return WriteResultResponse(
            success=result.success,
            skipped=result.skipped,
            skip_reason=result.skip_reason,
            error=result.error,
            fact_id=result.fact.fact_id if result.fact else None,
        )

    @router.get("/recall", response_model=list[TopicFile], tags=["memory"])
    async def recall(
        request: Request,
        query: str = Query(..., min_length=1, max_length=1000),
        top_k: int = Query(3, ge=1, le=20),
        verify: bool = False,
    ) -> list[TopicFile]:
        """Return up to ``top_k`` matching topic files."""
        return await get_manager(request).recall(query, top_k, verify)

    @router.post("/forget", response_model=dict[str, bool], tags=["memory"])
    async def forget(payload: ForgetRequest, request: Request) -> dict[str, bool]:
        """Forget one fact or an entire topic."""
        removed = await get_manager(request).forget(payload.topic_id, payload.fact_id)
        if removed:
            publish(
                request,
                "memory.forgotten",
                topic_id=payload.topic_id,
                fact_id=payload.fact_id,
            )
        return {"forgotten": removed}

    @router.post("/update", response_model=dict[str, bool], tags=["memory"])
    async def update(payload: UpdateRequest, request: Request) -> dict[str, bool]:
        """Update fact content or confidence, requiring evidence for verification."""
        changed = await get_manager(request).update(
            payload.topic_id,
            payload.fact_id,
            payload.new_content,
            payload.new_confidence,
            payload.verification_source,
        )
        if changed:
            publish(
                request,
                "memory.updated",
                topic_id=payload.topic_id,
                fact_id=payload.fact_id,
            )
        return {"updated": changed}

    @router.post("/context", response_model=ContextResponse, tags=["context"])
    async def context(payload: ContextRequest, request: Request) -> ContextResponse:
        """Build a bandwidth-aware context window."""
        built = await get_manager(request).build_context(
            payload.query,
            payload.max_topics,
            payload.token_budget,
        )
        return ContextResponse(text=built.text, **built.to_dict())

    @router.post(
        "/dream",
        response_model=dict[str, Any],
        tags=["consolidation"],
        dependencies=[Depends(enforce_dream_rate_limit)],
    )
    async def dream(payload: DreamRequest, request: Request) -> dict[str, Any]:
        """Run one consolidation cycle and emit ``consolidation.completed``."""
        result = await get_manager(request).dream_now(
            force=payload.force,
            max_tokens=settings.max_llm_tokens,
        )
        publish(
            request,
            "consolidation.completed",
            run_id=result.run_id,
            status=result.status,
            operations_applied=result.operations_applied,
        )
        return result.to_dict()

    @router.post("/prune", response_model=PruneResponse, tags=["memory"])
    async def prune(request: Request) -> PruneResponse:
        """Remove empty index pointers."""
        removed = await get_manager(request).prune()
        if removed:
            publish(request, "memory.pruned", pointers_removed=removed)
        return PruneResponse(pointers_removed=removed)

    @router.get("/index", response_model=IndexResponse, tags=["context"])
    async def get_index(request: Request) -> IndexResponse:
        """Return the generated ``MEMORY.md`` index."""
        return IndexResponse(index=await get_manager(request).get_context_injection())

    @router.post("/grep", response_model=list[dict[str, Any]], tags=["transcripts"])
    async def grep(payload: GrepRequest, request: Request) -> list[dict[str, Any]]:
        """Search archived transcript turns by substring or validated regex."""
        return await get_manager(request).grep_transcripts(
            payload.pattern,
            payload.max_results,
            payload.regex,
        )

    @app.websocket("/events")
    async def websocket_events(websocket: WebSocket) -> None:
        """Stream memory events to an authenticated WebSocket client.

        The API key is sent in ``X-API-Key`` or ``Authorization: Bearer``
        handshake headers. Messages conform to :class:`EventMessage`.
        """
        connection_id = uuid.uuid4().hex
        fingerprint = auth.verify(
            websocket.headers.get("x-api-key"),
            websocket.headers.get("authorization"),
        )
        if fingerprint is None:
            audit("websocket.auth_failure", connection_id=connection_id)
            await websocket.close(code=1008, reason="Invalid API key")
            return
        if not await limiter.acquire(fingerprint):
            audit(
                "websocket.rate_limited",
                connection_id=connection_id,
                client_id=fingerprint,
            )
            await websocket.close(code=1013, reason="Rate limit exceeded")
            return
        if not events.can_subscribe():
            audit(
                "websocket.rejected",
                connection_id=connection_id,
                client_id=fingerprint,
                reason="max_subscribers",
            )
            await websocket.close(code=1013, reason="Too many connections")
            return
        await websocket.accept()
        audit("websocket.connected", connection_id=connection_id, client_id=fingerprint)
        try:
            async with events.subscription() as queue:
                try:
                    while True:
                        await websocket.send_json(await queue.get())
                except (WebSocketDisconnect, RuntimeError):
                    audit("websocket.disconnected", connection_id=connection_id)
                    return
        except ResourceLimitError:
            audit(
                "websocket.rejected",
                connection_id=connection_id,
                client_id=fingerprint,
                reason="max_subscribers",
            )
            await websocket.close(code=1013, reason="Too many connections")

    app.include_router(router)
    return app
