from fastapi import APIRouter, HTTPException, Response, status

from app.dependencies import CurrentUserDep, StoreDep
from app.schemas import Conversation, ConversationList, ConversationSave


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.post("", response_model=Conversation)
def save_conversation(payload: ConversationSave, user: CurrentUserDep, store: StoreDep) -> Conversation:
    saved = store.save_conversation(user.uid, payload.model_dump(mode="json"))
    return Conversation.model_validate(saved)


@router.get("", response_model=ConversationList)
def list_conversations(user: CurrentUserDep, store: StoreDep) -> ConversationList:
    conversation = store.get_conversation(user.uid)
    if not conversation:
        return ConversationList(total=0, items=[])
    return ConversationList(total=1, items=[Conversation.model_validate(conversation)])


@router.get("/{conversation_id}", response_model=Conversation)
def get_conversation(conversation_id: str, user: CurrentUserDep, store: StoreDep) -> Conversation:
    if conversation_id != "primary":
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    conversation = store.get_conversation(user.uid)
    if not conversation:
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    return Conversation.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, user: CurrentUserDep, store: StoreDep) -> Response:
    if conversation_id != "primary" or not store.delete_conversation(user.uid):
        raise HTTPException(status_code=404, detail="대화를 찾을 수 없습니다.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
