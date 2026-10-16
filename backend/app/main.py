from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import account, ai, conversations, data, profile


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="내 운동 기록을 이해하는 다정한 AI 운동 비서 API",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Debug-User"],
    )
    app.include_router(profile.router)
    app.include_router(data.router)
    app.include_router(conversations.router)
    app.include_router(ai.router)
    app.include_router(account.router)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "ileona"}

    return app


app = create_app()
