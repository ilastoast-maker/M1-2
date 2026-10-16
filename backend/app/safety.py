from app.schemas import ProfileInput


def calculate_bmi(height_cm: float, weight_kg: float) -> float:
    return round(weight_kg / ((height_cm / 100) ** 2), 1)


def bmi_guidance(bmi: float) -> str | None:
    if bmi < 17:
        return (
            "입력한 키와 체중을 기준으로 일반적인 성인 범위보다 많이 낮아 보여요. "
            "지금은 감량이나 활동 목표 상향보다 안전을 먼저 살펴보고 전문가와 상담해 주세요."
        )
    if bmi >= 30:
        return (
            "꾸준히 움직이려는 시도 자체가 좋은 출발이에요. "
            "최근 기록을 기준으로 무리하지 않는 작은 활동 목표부터 시작해 보세요."
        )
    return None


def profile_bmi(profile: ProfileInput | dict) -> float:
    if isinstance(profile, dict):
        return calculate_bmi(profile["height_cm"], profile["current_weight_kg"])
    return calculate_bmi(profile.height_cm, profile.current_weight_kg)
