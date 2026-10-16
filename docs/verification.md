# 검증 기록

검증일: 2026-10-16

## 완료한 점검

- Git 원격 저장소가 `https://github.com/ilastoast-maker/M1-2.git`로 연결됨
- JSON 설정 파일 파싱 확인
- HTML `id` 77개가 중복 없이 정의됨
- UTF-8 한글 문서와 화면 문구 확인
- 환경 변수 이름 외에 API 키·서비스 계정·개인 Samsung Health 파일명이 저장소에 포함되지 않았음을 검색으로 확인
- Edge 헤드리스 렌더링으로 로그인 화면의 데스크톱 표시 확인
- 삼성 헬스 내보내기 파일을 저장소 밖에서 읽어 활동 데이터 389일과 필드 변환 규칙을 확인

## 실행 환경 때문에 남은 점검

현재 작업 환경에는 Python, Node.js, npm 실행 파일이 없어 다음 명령은 아직 실행하지 못했다.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --reload
```

Firebase 및 OpenAI 자격 증명이 준비된 뒤에는 Google 로그인, Firestore 사용자 격리, 이미지 추출, 실제 AI 응답을 통합 검증해야 한다. 배포 후에는 Render `/docs`와 Vercel 모바일 화면도 최종 확인한다.

## 배포 전 수동 체크리스트

- Firebase Authentication에서 Google 공급자 활성화
- Firestore 생성 및 `firestore.rules` 배포
- Render 환경 변수 설정 후 `/health`, `/docs` 확인
- Vercel 환경 변수 설정 후 Google 로그인 도메인 등록
- 서로 다른 두 계정으로 기록·대화가 섞이지 않는지 확인
- 실제 삼성 헬스 스크린샷에서 네 지표를 추출하고 수정 후 저장
- 0보 활동일, 중복 날짜 덮어쓰기, 체중 알림 건너뛰기 확인
- 의료 질문 거절과 BMI 17 미만 목표 상향 억제 확인
- 계정 삭제 후 프로필·기록·대화·Firebase Auth 사용자가 삭제되는지 확인
