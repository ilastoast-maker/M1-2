from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
from firebase_admin import auth
from pydantic import BaseModel

from app.config import get_settings
from app.dependencies import CurrentUserDep, StoreDep


router = APIRouter(prefix="/api/account", tags=["account"])


class DeleteAccountRequest(BaseModel):
    confirmation: Literal["DELETE"]


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(payload: DeleteAccountRequest, user: CurrentUserDep, store: StoreDep) -> Response:
    if payload.confirmation != "DELETE":
        raise HTTPException(status_code=400, detail="삭제 확인 문구가 일치하지 않습니다.")
    store.delete_user(user.uid)
    if get_settings().auth_mode == "firebase":
        auth.delete_user(user.uid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
