from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config import get_settings
from app.dependencies import CurrentUserDep, StoreDep
from app.schemas import ChatRequest, ChatResponse, Conversation, Message, MessageRole, ScreenshotExtraction
from app.services.ai import AIService, AIUnavailableError, exercise_scope_response
from app.services.rate_limit import RateLimitExceeded, limiter
from app.services.summary import build_summary


router = APIRouter(prefix="/api", tags=["ai"])
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PIXELS = 16_000_000


def _safe_image(raw: bytes, claimed_type: str | None) -> tuple[bytes, str]:
    settings = get_settings()
    if not raw or len(raw) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="이미지는 5MB 이하만 업로드할 수 있습니다.")
    if claimed_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail="JPEG, PNG, WebP 이미지만 사용할 수 있습니다.")
    try:
        with Image.open(BytesIO(raw)) as image:
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            if image.width * image.height > MAX_PIXELS:
                raise HTTPException(status_code=413, detail="이미지 해상도가 너무 큽니다.")
            image.thumbnail((2048, 2048))
            normalized = image.convert("RGB")
            output = BytesIO()
            normalized.save(output, format="JPEG", quality=90, optimize=True)
            return output.getvalue(), "image/jpeg"
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=415, detail="올바른 이미지 파일이 아닙니다.") from exc


@router.post("/data/import/screenshot", response_model=ScreenshotExtraction)
def extract_screenshot(
    user: CurrentUserDep,
    image: UploadFile = File(...),
    consent: bool = Form(...),
) -> ScreenshotExtraction:
    if not consent:
        raise HTTPException(status_code=400, detail="이미지의 OpenAI 처리에 동의해야 합니다.")
    try:
        limiter.check(f"image:{user.uid}", limit=10)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail="시간당 이미지 분석 횟수를 초과했습니다.") from exc
    raw = image.file.read(get_settings().max_image_bytes + 1)
    safe_bytes, media_type = _safe_image(raw, image.content_type)
    try:
        return AIService(get_settings()).extract_activity(safe_bytes, media_type)
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, user: CurrentUserDep, store: StoreDep) -> ChatResponse:
    try:
        limiter.check(f"chat:{user.uid}", limit=30)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=429, detail="시간당 대화 요청 횟수를 초과했습니다.") from exc
    profile = store.get_profile(user.uid)
    if not profile:
        raise HTTPException(status_code=409, detail="프로필을 먼저 설정해 주세요.")
    records = store.list_records(user.uid)
    summary = build_summary(records, profile.get("step_goal"))
    conversation = store.get_conversation(user.uid) or {"messages": [], "summary": ""}
    answer = exercise_scope_response(payload.message)
    if not answer:
        try:
            answer = AIService(get_settings()).chat(payload.message, summary, profile, conversation["messages"])
        except AIUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    now = datetime.now(timezone.utc)
    new_messages = [
        Message(role=MessageRole.USER, content=payload.message, created_at=now),
        Message(role=MessageRole.ASSISTANT, content=answer, created_at=datetime.now(timezone.utc)),
    ]
    saved = store.save_conversation(
        user.uid,
        {"messages": [message.model_dump(mode="json") for message in new_messages]},
    )
    return ChatResponse(answer=answer, conversation=Conversation.model_validate(saved))
