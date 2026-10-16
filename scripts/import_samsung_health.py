"""Preview or import Samsung Health daily activity records without storing the ZIP.

Examples:
  python scripts/import_samsung_health.py export.zip
  python scripts/import_samsung_health.py export.zip --apply --api http://localhost:8000 --debug-user demo-user
  python scripts/import_samsung_health.py export.zip --apply --api https://example.onrender.com --token FIREBASE_ID_TOKEN
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path


TARGET_SUFFIX = "com.samsung.shealth.activity.day_summary"


@dataclass(frozen=True)
class Activity:
    day: str
    steps: int
    active_minutes: int
    calories: float
    distance_km: float

    def as_api_payload(self) -> dict:
        return {
            "date": self.day,
            "value": self.steps,
            "memo": "Samsung Health 내보내기",
            "record_type": "activity",
            "source": "samsung_export",
            "active_minutes": self.active_minutes,
            "activity_calories": self.calories,
            "distance_km": self.distance_km,
        }


def find_activity_csv(archive: zipfile.ZipFile) -> str:
    matches = [
        name
        for name in archive.namelist()
        if TARGET_SUFFIX in Path(name).name and name.lower().endswith(".csv")
    ]
    if len(matches) != 1:
        raise ValueError(f"일일 활동 CSV를 하나만 찾을 수 있어야 합니다. 발견: {len(matches)}")
    return matches[0]


def parse_archive(path: Path) -> list[Activity]:
    with zipfile.ZipFile(path) as archive:
        target = find_activity_csv(archive)
        raw = archive.read(target).decode("utf-8-sig")
    lines = raw.splitlines()
    if len(lines) < 3:
        raise ValueError("일일 활동 CSV에 데이터가 없습니다.")
    reader = csv.DictReader(io.StringIO("\n".join(lines[1:])))
    by_day: dict[str, Activity] = {}
    for row in reader:
        day = row["day_time"][:10]
        date.fromisoformat(day)
        walk_ms = float(row.get("walk_time") or 0)
        run_ms = float(row.get("run_time") or 0)
        by_day[day] = Activity(
            day=day,
            steps=int(float(row.get("step_count") or 0)),
            active_minutes=round((walk_ms + run_ms) / 60_000),
            calories=round(float(row.get("calorie") or 0), 1),
            distance_km=round(float(row.get("distance") or 0) / 1000, 2),
        )
    return [by_day[key] for key in sorted(by_day)]


def upload(activity: Activity, api_base: str, token: str | None, debug_user: str | None) -> str:
    body = json.dumps(activity.as_api_payload()).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if debug_user:
        headers["X-Debug-User"] = debug_user
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/api/data?overwrite=true",
        data=body,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return str(response.status)


def main() -> int:
    parser = argparse.ArgumentParser(description="삼성 헬스 일일 활동 내보내기 가져오기")
    parser.add_argument("archive", type=Path)
    parser.add_argument("--apply", action="store_true", help="미리보기 대신 API에 저장")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--token", help="Firebase ID token")
    parser.add_argument("--debug-user", help="개발 모드 X-Debug-User")
    args = parser.parse_args()

    activities = parse_archive(args.archive)
    if not activities:
        print("가져올 활동 기록이 없습니다.")
        return 1

    print(f"일일 활동 {len(activities)}개: {activities[0].day} ~ {activities[-1].day}")
    print("원본 ZIP과 세부 건강 데이터는 업로드하지 않습니다.")
    if not args.apply:
        print("미리보기만 완료했습니다. 저장하려면 --apply를 추가하세요.")
        return 0

    if not args.token and not args.debug_user:
        parser.error("--apply에는 --token 또는 개발용 --debug-user가 필요합니다.")

    success = 0
    for activity in activities:
        try:
            upload(activity, args.api, args.token, args.debug_user)
            success += 1
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            print(f"{activity.day} 저장 실패: HTTP {exc.code} {detail}", file=sys.stderr)
    print(f"저장 완료: {success}/{len(activities)}")
    return 0 if success == len(activities) else 2


if __name__ == "__main__":
    raise SystemExit(main())
