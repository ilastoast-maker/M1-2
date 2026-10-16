from __future__ import annotations

from datetime import date
from statistics import mean
from typing import Any

from app.schemas import ActivityMetrics, DataSummary, WeightMetrics


def _as_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def build_summary(records: list[dict[str, Any]], step_goal: int | None = None) -> DataSummary:
    if not records:
        return DataSummary(
            count=0,
            activity_count=0,
            weight_count=0,
            activity=ActivityMetrics(),
            weight=WeightMetrics(),
            trend="분석할 기록이 아직 없어요.",
        )

    activity = sorted(
        [item for item in records if str(item["record_type"]) == "activity"],
        key=lambda item: _as_date(item["date"]),
    )
    weight = sorted(
        [item for item in records if str(item["record_type"]) == "weight"],
        key=lambda item: _as_date(item["date"]),
    )
    all_dates = [_as_date(item["date"]) for item in records]

    steps = [int(round(float(item["value"]))) for item in activity]
    active_minutes = [int(item.get("active_minutes") or 0) for item in activity]
    calories = [float(item.get("activity_calories") or 0) for item in activity]
    distances = [float(item.get("distance_km") or 0) for item in activity]

    recent = steps[-7:]
    previous = steps[-14:-7]
    recent_average = round(mean(recent), 1) if recent else None
    trend = "최근 14일 기록이 모이면 추세를 알려드릴게요."
    if len(recent) == 7 and len(previous) == 7:
        previous_average = mean(previous)
        if previous_average == 0:
            trend = "최근 활동 기록이 새롭게 시작됐어요."
        else:
            change = ((mean(recent) - previous_average) / previous_average) * 100
            if change > 5:
                trend = f"최근 7일 평균 걸음 수가 이전 7일보다 {abs(change):.1f}% 증가했어요."
            elif change < -5:
                trend = f"최근 7일 평균 걸음 수가 이전 7일보다 {abs(change):.1f}% 감소했어요."
            else:
                trend = "최근 7일 걸음 수가 이전 주와 비슷하게 유지되고 있어요."

    weight_values = [float(item["value"]) for item in weight]
    weight_metrics = WeightMetrics()
    if weight_values:
        weight_metrics = WeightMetrics(
            latest_kg=round(weight_values[-1], 1),
            change_kg=round(weight_values[-1] - weight_values[0], 1) if len(weight_values) > 1 else 0,
            min_kg=round(min(weight_values), 1),
            max_kg=round(max(weight_values), 1),
        )

    activity_metrics = ActivityMetrics(
        total_steps=sum(steps),
        average_steps=round(mean(steps), 1) if steps else None,
        max_steps=max(steps) if steps else None,
        min_steps=min(steps) if steps else None,
        total_active_minutes=sum(active_minutes),
        average_active_minutes=round(mean(active_minutes), 1) if active_minutes else None,
        total_activity_calories=round(sum(calories), 1),
        total_distance_km=round(sum(distances), 2),
        goal_achievement_days=(sum(1 for value in steps if step_goal and value >= step_goal) if step_goal else 0),
    )

    return DataSummary(
        period_start=min(all_dates),
        period_end=max(all_dates),
        count=len(records),
        activity_count=len(activity),
        weight_count=len(weight),
        activity=activity_metrics,
        weight=weight_metrics,
        trend=trend,
        recent_average_steps=recent_average,
    )
