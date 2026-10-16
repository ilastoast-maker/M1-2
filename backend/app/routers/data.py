import csv
import io

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.dependencies import CurrentUserDep, StoreDep
from app.schemas import DataCreate, DataListResponse, DataRecord, DataSummary, DataUpdate, RecordType
from app.services.summary import build_summary
from app.store import DuplicateRecordError, record_key


router = APIRouter(prefix="/api/data", tags=["data"])


def _sync_weight_profile(user_id: str, store: StoreDep) -> None:
    profile = store.get_profile(user_id)
    if not profile:
        return
    weights = [item for item in store.list_records(user_id) if item["record_type"] == "weight"]
    if weights:
        store.save_profile(user_id, {"current_weight_kg": float(weights[0]["value"])})


@router.get("/summary", response_model=DataSummary)
def get_summary(user: CurrentUserDep, store: StoreDep) -> DataSummary:
    profile = store.get_profile(user.uid) or {}
    return build_summary(store.list_records(user.uid), profile.get("step_goal"))


@router.get("/export.csv")
def export_csv(user: CurrentUserDep, store: StoreDep) -> Response:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "date",
            "record_type",
            "value",
            "memo",
            "active_minutes",
            "activity_calories",
            "distance_km",
            "source",
        ],
        extrasaction="ignore",
    )
    writer.writeheader()
    for item in reversed(store.list_records(user.uid)):
        writer.writerow(item)
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="ileona-data.csv"'},
    )


@router.post("", response_model=DataRecord, status_code=status.HTTP_201_CREATED)
def create_data(
    payload: DataCreate,
    user: CurrentUserDep,
    store: StoreDep,
    overwrite: bool = Query(default=False),
) -> DataRecord:
    body = payload.model_dump(mode="json")
    try:
        saved = store.create_record(user.uid, body)
    except DuplicateRecordError as exc:
        if not overwrite:
            raise HTTPException(status_code=409, detail="해당 날짜와 유형의 기록이 이미 있습니다.") from exc
        existing_id = record_key(user.uid, payload.record_type.value, payload.date.isoformat())
        saved = store.update_record(user.uid, existing_id, body)
        if not saved:
            raise HTTPException(status_code=409, detail="기존 기록을 갱신하지 못했습니다.") from exc
    if payload.record_type == RecordType.WEIGHT:
        _sync_weight_profile(user.uid, store)
    return DataRecord.model_validate(saved)


@router.get("", response_model=DataListResponse)
def list_data(
    user: CurrentUserDep,
    store: StoreDep,
    record_type: RecordType | None = None,
    limit: int = Query(default=200, ge=1, le=500),
) -> DataListResponse:
    items = store.list_records(user.uid)
    if record_type:
        items = [item for item in items if item["record_type"] == record_type.value]
    items = items[:limit]
    return DataListResponse(total=len(items), items=[DataRecord.model_validate(item) for item in items])


@router.put("/{record_id}", response_model=DataRecord)
def update_data(record_id: str, payload: DataUpdate, user: CurrentUserDep, store: StoreDep) -> DataRecord:
    existing = store.get_record(user.uid, record_id)
    if not existing:
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    changes = payload.model_dump(mode="json", exclude_unset=True)
    candidate = DataCreate.model_validate({**existing, **changes})
    try:
        saved = store.update_record(user.uid, record_id, changes)
    except DuplicateRecordError as exc:
        raise HTTPException(status_code=409, detail="변경할 날짜에 같은 유형의 기록이 있습니다.") from exc
    if candidate.record_type == RecordType.WEIGHT:
        _sync_weight_profile(user.uid, store)
    return DataRecord.model_validate(saved)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_data(record_id: str, user: CurrentUserDep, store: StoreDep) -> Response:
    existing = store.get_record(user.uid, record_id)
    if not existing or not store.delete_record(user.uid, record_id):
        raise HTTPException(status_code=404, detail="기록을 찾을 수 없습니다.")
    if existing["record_type"] == "weight":
        _sync_weight_profile(user.uid, store)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
