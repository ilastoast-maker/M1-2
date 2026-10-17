from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from threading import RLock
from typing import Any, Protocol
from uuid import uuid4

import firebase_admin
from firebase_admin import credentials, firestore

from app.config import get_settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DuplicateRecordError(Exception):
    """Raised when a user already has the record type for a date."""


class Store(Protocol):
    def get_profile(self, user_id: str) -> dict[str, Any] | None: ...
    def save_profile(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def create_record(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def list_records(self, user_id: str) -> list[dict[str, Any]]: ...
    def get_record(self, user_id: str, record_id: str) -> dict[str, Any] | None: ...
    def update_record(self, user_id: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any] | None: ...
    def delete_record(self, user_id: str, record_id: str) -> bool: ...
    def get_conversation(self, user_id: str) -> dict[str, Any] | None: ...
    def save_conversation(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...
    def delete_conversation(self, user_id: str) -> bool: ...
    def delete_user(self, user_id: str) -> None: ...


def record_key(user_id: str, record_type: str, record_date: str) -> str:
    raw = f"{user_id}:{record_type}:{record_date}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


class MemoryStore:
    def __init__(self) -> None:
        self.profiles: dict[str, dict[str, Any]] = {}
        self.records: dict[str, dict[str, Any]] = {}
        self.conversations: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def clear(self) -> None:
        with self._lock:
            self.profiles.clear()
            self.records.clear()
            self.conversations.clear()

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            profile = self.profiles.get(user_id)
            return deepcopy(profile) if profile else None

    def save_profile(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            existing = self.profiles.get(user_id, {})
            now = utc_now()
            saved = {
                **existing,
                **deepcopy(payload),
                "user_id": user_id,
                "created_at": existing.get("created_at", now),
                "updated_at": now,
            }
            self.profiles[user_id] = saved
            return deepcopy(saved)

    def create_record(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            record_id = record_key(user_id, str(payload["record_type"]), str(payload["date"]))
            if record_id in self.records:
                raise DuplicateRecordError
            now = utc_now()
            saved = {
                **deepcopy(payload),
                "id": record_id,
                "user_id": user_id,
                "created_at": now,
                "updated_at": now,
            }
            self.records[record_id] = saved
            return deepcopy(saved)

    def list_records(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            items = [deepcopy(item) for item in self.records.values() if item["user_id"] == user_id]
        return sorted(items, key=lambda item: (str(item["date"]), item["record_type"]), reverse=True)

    def get_record(self, user_id: str, record_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self.records.get(record_id)
            if not item or item["user_id"] != user_id:
                return None
            return deepcopy(item)

    def update_record(self, user_id: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            existing = self.records.get(record_id)
            if not existing or existing["user_id"] != user_id:
                return None
            if "date" in payload and str(payload["date"]) != str(existing["date"]):
                new_id = record_key(user_id, existing["record_type"], str(payload["date"]))
                if new_id in self.records:
                    raise DuplicateRecordError
                del self.records[record_id]
                record_id = new_id
            saved = {**existing, **deepcopy(payload), "id": record_id, "updated_at": utc_now()}
            self.records[record_id] = saved
            return deepcopy(saved)

    def delete_record(self, user_id: str, record_id: str) -> bool:
        with self._lock:
            existing = self.records.get(record_id)
            if not existing or existing["user_id"] != user_id:
                return False
            del self.records[record_id]
            return True

    def get_conversation(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self.conversations.get(user_id)
            return deepcopy(item) if item else None

    def save_conversation(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            existing = self.conversations.get(user_id, {})
            now = utc_now()
            messages = [*existing.get("messages", []), *deepcopy(payload.get("messages", []))]
            saved = {
                **existing,
                **deepcopy(payload),
                "messages": messages[-200:],
                "id": "primary",
                "user_id": user_id,
                "created_at": existing.get("created_at", now),
                "updated_at": now,
            }
            self.conversations[user_id] = saved
            return deepcopy(saved)

    def delete_conversation(self, user_id: str) -> bool:
        with self._lock:
            return self.conversations.pop(user_id, None) is not None

    def delete_user(self, user_id: str) -> None:
        with self._lock:
            self.profiles.pop(user_id, None)
            self.conversations.pop(user_id, None)
            for record_id in [key for key, value in self.records.items() if value["user_id"] == user_id]:
                del self.records[record_id]


class FirestoreStore:
    def __init__(self) -> None:
        initialize_firebase()
        self.db = firestore.client()

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        snapshot = self.db.collection("profiles").document(user_id).get()
        return snapshot.to_dict() if snapshot.exists else None

    def save_profile(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ref = self.db.collection("profiles").document(user_id)
        existing = ref.get().to_dict() or {}
        now = utc_now()
        saved = {
            **existing,
            **payload,
            "user_id": user_id,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }
        ref.set(saved)
        return saved

    def create_record(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        record_id = record_key(user_id, str(payload["record_type"]), str(payload["date"]))
        ref = self.db.collection("data").document(record_id)
        if ref.get().exists:
            raise DuplicateRecordError
        now = utc_now()
        saved = {
            **payload,
            "id": record_id,
            "user_id": user_id,
            "created_at": now,
            "updated_at": now,
        }
        ref.set(saved)
        return saved

    def list_records(self, user_id: str) -> list[dict[str, Any]]:
        query = self.db.collection("data").where("user_id", "==", user_id)
        items = [snapshot.to_dict() for snapshot in query.stream()]
        return sorted(items, key=lambda item: (str(item["date"]), item["record_type"]), reverse=True)

    def get_record(self, user_id: str, record_id: str) -> dict[str, Any] | None:
        snapshot = self.db.collection("data").document(record_id).get()
        item = snapshot.to_dict() if snapshot.exists else None
        return item if item and item.get("user_id") == user_id else None

    def update_record(self, user_id: str, record_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        existing = self.get_record(user_id, record_id)
        if not existing:
            return None
        new_id = record_id
        if "date" in payload and str(payload["date"]) != str(existing["date"]):
            new_id = record_key(user_id, existing["record_type"], str(payload["date"]))
            new_ref = self.db.collection("data").document(new_id)
            if new_ref.get().exists:
                raise DuplicateRecordError
            self.db.collection("data").document(record_id).delete()
        saved = {**existing, **payload, "id": new_id, "updated_at": utc_now()}
        self.db.collection("data").document(new_id).set(saved)
        return saved

    def delete_record(self, user_id: str, record_id: str) -> bool:
        if not self.get_record(user_id, record_id):
            return False
        self.db.collection("data").document(record_id).delete()
        return True

    def get_conversation(self, user_id: str) -> dict[str, Any] | None:
        ref = self.db.collection("conversations").document(user_id)
        snapshot = ref.get()
        if not snapshot.exists:
            return None
        metadata = snapshot.to_dict() or {}
        message_query = ref.collection("messages").order_by("created_at").limit_to_last(200)
        metadata["messages"] = [message.to_dict() for message in message_query.get()]
        return metadata

    def save_conversation(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        ref = self.db.collection("conversations").document(user_id)
        existing = ref.get().to_dict() or {}
        now = utc_now()
        saved = {
            **existing,
            "summary": payload.get("summary", existing.get("summary", "")),
            "id": "primary",
            "user_id": user_id,
            "created_at": existing.get("created_at", now),
            "updated_at": now,
        }
        ref.set(saved)
        messages = payload.get("messages", [])
        if messages:
            batch = self.db.batch()
            for message in messages:
                message_ref = ref.collection("messages").document(uuid4().hex)
                batch.set(message_ref, message)
            batch.commit()
        return self.get_conversation(user_id) or {**saved, "messages": []}

    def delete_conversation(self, user_id: str) -> bool:
        ref = self.db.collection("conversations").document(user_id)
        if not ref.get().exists:
            return False
        while True:
            messages = list(ref.collection("messages").limit(400).stream())
            if not messages:
                break
            batch = self.db.batch()
            for message in messages:
                batch.delete(message.reference)
            batch.commit()
        ref.delete()
        return True

    def delete_user(self, user_id: str) -> None:
        for item in self.list_records(user_id):
            self.db.collection("data").document(item["id"]).delete()
        self.delete_conversation(user_id)
        self.db.collection("profiles").document(user_id).delete()


_memory_store = MemoryStore()


def initialize_firebase() -> None:
    settings = get_settings()
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass
    if not settings.firebase_service_account_json:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON is required")
    service_account = json.loads(settings.firebase_service_account_json)
    firebase_admin.initialize_app(credentials.Certificate(service_account))


@lru_cache
def get_store() -> Store:
    if get_settings().use_in_memory_db:
        return _memory_store
    return FirestoreStore()


def reset_store_cache() -> None:
    get_store.cache_clear()
    _memory_store.clear()
