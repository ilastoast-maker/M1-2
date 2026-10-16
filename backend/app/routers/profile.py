from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, status

from app.config import get_settings
from app.dependencies import CurrentUserDep, StoreDep
from app.safety import bmi_guidance, calculate_bmi
from app.schemas import (
    DataCreate,
    ProfileInput,
    ProfileResponse,
    RecordSource,
    RecordType,
    StepGoalAccept,
    StepGoalRecommendation,
)
from app.services.ai import AIService, AIUnavailableError
from app.services.summary import build_summary
from app.store import DuplicateRecordError, record_key


router = APIRouter(prefix="/api/profile", tags=["profile"])


def _profile_response(profile: dict) -> ProfileResponse:
    bmi = calculate_bmi(float(profile["height_cm"]), float(profile["current_weight_kg"]))
    return ProfileResponse.model_validate({**profile, "bmi": bmi, "bmi_guidance": bmi_guidance(bmi)})


@router.get("", response_model=ProfileResponse)
def get_profile(user: CurrentUserDep, store: StoreDep) -> ProfileResponse:
    profile = store.get_profile(user.uid)
    if not profile:
        raise HTTPException(status_code=404, detail="프로필을 먼저 설정해 주세요.")
    return _profile_response(profile)


@router.put("", response_model=ProfileResponse)
def save_profile(payload: ProfileInput, user: CurrentUserDep, store: StoreDep) -> ProfileResponse:
    existing = store.get_profile(user.uid)
    saved = store.save_profile(user.uid, payload.model_dump(mode="json"))
    if not existing or float(existing.get("current_weight_kg", 0)) != payload.current_weight_kg:
        today = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
        weight_payload = DataCreate(
            date=today,
            value=payload.current_weight_kg,
            memo="프로필 체중",
            record_type=RecordType.WEIGHT,
            source=RecordSource.MANUAL,
        ).model_dump(mode="json")
        try:
            store.create_record(user.uid, weight_payload)
        except DuplicateRecordError:
            weight_id = record_key(user.uid, RecordType.WEIGHT.value, today)
            store.update_record(user.uid, weight_id, weight_payload)
    return _profile_response(saved)


@router.post("/weight", status_code=status.HTTP_201_CREATED)
def add_weight(payload: DataCreate, user: CurrentUserDep, store: StoreDep) -> dict:
    if payload.record_type != RecordType.WEIGHT:
        raise HTTPException(status_code=422, detail="체중 기록만 이 경로에 저장할 수 있습니다.")
    profile = store.get_profile(user.uid)
    if not profile:
        raise HTTPException(status_code=409, detail="프로필을 먼저 설정해 주세요.")
    try:
        saved = store.create_record(
            user.uid,
            payload.model_copy(update={"source": RecordSource.MANUAL}).model_dump(mode="json"),
        )
    except DuplicateRecordError as exc:
        raise HTTPException(status_code=409, detail="해당 날짜의 체중 기록이 이미 있습니다.") from exc
    weight_records = [item for item in store.list_records(user.uid) if item["record_type"] == "weight"]
    if weight_records and weight_records[0]["id"] == saved["id"]:
        store.save_profile(user.uid, {"current_weight_kg": payload.value})
    return saved


@router.post("/step-goal/recommend", response_model=StepGoalRecommendation)
def recommend_step_goal(user: CurrentUserDep, store: StoreDep) -> StepGoalRecommendation:
    profile = store.get_profile(user.uid)
    if not profile:
        raise HTTPException(status_code=409, detail="프로필을 먼저 설정해 주세요.")
    summary = build_summary(store.list_records(user.uid), profile.get("step_goal"))
    try:
        recommendation = AIService(get_settings()).recommend_step_goal(summary, profile)
    except AIUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    store.save_profile(
        user.uid,
        {
            "pending_step_goal": recommendation.recommended_steps,
            "step_goal_recommended_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return recommendation


@router.post("/step-goal/accept", response_model=ProfileResponse)
def accept_step_goal(payload: StepGoalAccept, user: CurrentUserDep, store: StoreDep) -> ProfileResponse:
    profile = store.get_profile(user.uid)
    if not profile:
        raise HTTPException(status_code=409, detail="프로필을 먼저 설정해 주세요.")
    if profile.get("pending_step_goal") != payload.steps:
        raise HTTPException(status_code=409, detail="현재 대기 중인 추천과 일치하지 않습니다.")
    saved = store.save_profile(
        user.uid,
        {"step_goal": payload.steps, "pending_step_goal": None, "step_goal_accepted_at": datetime.now(timezone.utc).isoformat()},
    )
    return _profile_response(saved)
