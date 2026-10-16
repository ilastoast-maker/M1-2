from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth

from app.config import Settings, get_settings
from app.store import Store, get_store, initialize_firebase


@dataclass(frozen=True)
class CurrentUser:
    uid: str


bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
    debug_user: Annotated[str | None, Header(alias="X-Debug-User")] = None,
) -> CurrentUser:
    if settings.auth_mode == "dev":
        return CurrentUser(uid=(debug_user or "demo-user")[:128])

    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        initialize_firebase()
        decoded = auth.verify_id_token(credentials.credentials, check_revoked=True)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인 정보가 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    uid = decoded.get("uid") or decoded.get("sub")
    if not uid:
        raise HTTPException(status_code=401, detail="사용자 식별자를 확인할 수 없습니다.")
    return CurrentUser(uid=str(uid))


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
StoreDep = Annotated[Store, Depends(get_store)]
