from datetime import date, date as Date, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator, model_validator


class Sex(StrEnum):
    MALE = "male"
    FEMALE = "female"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class RecordType(StrEnum):
    ACTIVITY = "activity"
    WEIGHT = "weight"


class RecordSource(StrEnum):
    MANUAL = "manual"
    SCREENSHOT = "screenshot"
    SAMSUNG_EXPORT = "samsung_export"


class ProfileInput(BaseModel):
    age: int = Field(ge=19, le=100)
    sex: Sex
    height_cm: float = Field(ge=120, le=230)
    current_weight_kg: float = Field(ge=30, le=300)
    target_weight_kg: float = Field(ge=30, le=300)
    low_bmi_goal_confirmed: bool = False

    @model_validator(mode="after")
    def confirm_very_low_target(self) -> "ProfileInput":
        target_bmi = self.target_weight_kg / ((self.height_cm / 100) ** 2)
        if target_bmi < 17 and not self.low_bmi_goal_confirmed:
            raise ValueError("BMI 17 미만의 목표 체중은 별도 확인이 필요합니다.")
        return self


class ProfileResponse(ProfileInput):
    user_id: str
    bmi: float
    bmi_guidance: str | None = None
    step_goal: int | None = None
    pending_step_goal: int | None = None
    last_weight_prompt_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DataRecordBase(BaseModel):
    date: date
    value: float = Field(ge=0, le=1_000_000)
    memo: str = Field(default="", max_length=500)
    record_type: RecordType
    source: RecordSource = RecordSource.MANUAL
    active_minutes: int | None = Field(default=None, ge=0, le=1440)
    activity_calories: float | None = Field(default=None, ge=0, le=20_000)
    distance_km: float | None = Field(default=None, ge=0, le=1000)

    @field_validator("date")
    @classmethod
    def date_cannot_be_future(cls, value: date) -> date:
        if value > datetime.now(ZoneInfo("Asia/Seoul")).date():
            raise ValueError("미래 날짜에는 기록을 저장할 수 없습니다.")
        return value

    @model_validator(mode="after")
    def validate_type_specific_value(self) -> "DataRecordBase":
        if self.record_type == RecordType.ACTIVITY and self.value > 200_000:
            raise ValueError("걸음 수는 200,000보 이하여야 합니다.")
        if self.record_type == RecordType.WEIGHT:
            if not 30 <= self.value <= 300:
                raise ValueError("체중은 30kg 이상 300kg 이하여야 합니다.")
            if any(value is not None for value in (self.active_minutes, self.activity_calories, self.distance_km)):
                raise ValueError("체중 기록에는 활동 지표를 포함할 수 없습니다.")
        return self


class DataCreate(DataRecordBase):
    pass


class DataUpdate(BaseModel):
    date: Date | None = None
    value: float | None = Field(default=None, ge=0, le=1_000_000)
    memo: str | None = Field(default=None, max_length=500)
    active_minutes: int | None = Field(default=None, ge=0, le=1440)
    activity_calories: float | None = Field(default=None, ge=0, le=20_000)
    distance_km: float | None = Field(default=None, ge=0, le=1000)


class DataRecord(DataRecordBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime


class DataListResponse(BaseModel):
    total: int
    items: list[DataRecord]


class ActivityMetrics(BaseModel):
    total_steps: int = 0
    average_steps: float | None = None
    max_steps: int | None = None
    min_steps: int | None = None
    total_active_minutes: int = 0
    average_active_minutes: float | None = None
    total_activity_calories: float = 0
    total_distance_km: float = 0
    goal_achievement_days: int = 0


class WeightMetrics(BaseModel):
    latest_kg: float | None = None
    change_kg: float | None = None
    min_kg: float | None = None
    max_kg: float | None = None


class DataSummary(BaseModel):
    period_start: date | None = None
    period_end: date | None = None
    count: int
    activity_count: int
    weight_count: int
    activity: ActivityMetrics
    weight: WeightMetrics
    trend: str
    recent_average_steps: float | None = None


class ScreenshotExtraction(BaseModel):
    steps: int = Field(ge=0, le=200_000)
    active_minutes: int = Field(ge=0, le=1440)
    activity_calories: float = Field(ge=0, le=20_000)
    distance_km: float = Field(ge=0, le=1000)
    confidence: str = Field(pattern="^(high|medium|low)$")
    warnings: list[str] = Field(default_factory=list)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    role: MessageRole
    content: str = Field(min_length=1, max_length=4000)
    created_at: datetime


class ConversationSave(BaseModel):
    messages: list[Message] = Field(max_length=200)


class Conversation(BaseModel):
    id: str = "primary"
    user_id: str
    messages: list[Message]
    summary: str = ""
    created_at: datetime
    updated_at: datetime


class ConversationList(BaseModel):
    total: int
    items: list[Conversation]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    conversation: Conversation


class StepGoalRecommendation(BaseModel):
    recommended_steps: int = Field(ge=1000, le=20_000, multiple_of=100)
    reason: str
    safety_notice: str | None = None


class StepGoalAccept(BaseModel):
    steps: int = Field(ge=1000, le=20_000, multiple_of=100)
