import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional, cast

from chainlit.data.base import BaseDataLayer
from chainlit.element import ElementDict
from chainlit.step import StepDict
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class LocalJSONDataLayer(BaseDataLayer):
    """
    Minimal local persistence for Chainlit thread history.
    Stores users/threads/steps/elements in a JSON file so the sidebar history works
    without external services.
    """

    def __init__(self, store_path: str = ".files/deskpilot_history.json"):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._state: Dict[str, Any] = self._load_state()

    def _empty_state(self) -> Dict[str, Any]:
        return {
            "users": {},
            "threads": {},
            "feedbacks": {},
        }

    def _load_state(self) -> Dict[str, Any]:
        if not self.store_path.exists():
            state = self._empty_state()
            self._write_state(state)
            return state

        try:
            raw = json.loads(self.store_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("History store is not a JSON object.")
            for key in ("users", "threads", "feedbacks"):
                if key not in raw or not isinstance(raw[key], dict):
                    raw[key] = {}
            return raw
        except Exception:
            state = self._empty_state()
            self._write_state(state)
            return state

    def _write_state(self, state: Dict[str, Any]) -> None:
        self.store_path.write_text(
            json.dumps(state, ensure_ascii=True, indent=2),
            encoding="utf-8",
        )

    def _persist(self) -> None:
        self._write_state(self._state)

    def _user_identifier_from_id(self, user_id: str) -> Optional[str]:
        for identifier, user in self._state["users"].items():
            if user.get("id") == user_id:
                return str(identifier)
        return None

    def _ensure_thread(self, thread_id: str) -> ThreadDict:
        thread = self._state["threads"].get(thread_id)
        if thread is None:
            thread = {
                "id": thread_id,
                "createdAt": _now_iso(),
                "name": None,
                "userId": None,
                "userIdentifier": None,
                "tags": [],
                "metadata": {},
                "steps": [],
                "elements": [],
            }
            self._state["threads"][thread_id] = thread
        return cast(ThreadDict, thread)

    def _upsert_step_in_thread(self, thread: ThreadDict, step_dict: StepDict) -> None:
        steps = thread.get("steps", [])
        step_id = step_dict.get("id")
        for idx, existing in enumerate(steps):
            if step_id and existing.get("id") == step_id:
                steps[idx] = cast(StepDict, _json_safe(step_dict))
                break
        else:
            steps.append(cast(StepDict, _json_safe(step_dict)))
        thread["steps"] = cast(List[StepDict], steps)

    def _thread_last_updated(self, thread: ThreadDict) -> str:
        steps = thread.get("steps", [])
        if steps:
            sorted_steps = sorted(
                steps,
                key=lambda s: str(s.get("createdAt") or s.get("start") or ""),
            )
            latest = sorted_steps[-1]
            return str(latest.get("createdAt") or latest.get("start") or thread["createdAt"])
        return str(thread.get("createdAt") or "")

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        with self._lock:
            raw = self._state["users"].get(identifier)
            if not raw:
                return None
            return PersistedUser(
                id=str(raw["id"]),
                identifier=str(raw["identifier"]),
                createdAt=str(raw["createdAt"]),
                metadata=cast(Dict[str, Any], raw.get("metadata", {})),
            )

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        with self._lock:
            existing = self._state["users"].get(user.identifier)
            if existing:
                existing["metadata"] = _json_safe(user.metadata or {})
            else:
                self._state["users"][user.identifier] = {
                    "id": str(uuid.uuid4()),
                    "identifier": user.identifier,
                    "createdAt": _now_iso(),
                    "metadata": _json_safe(user.metadata or {}),
                }
            self._persist()

            created = self._state["users"][user.identifier]
            return PersistedUser(
                id=str(created["id"]),
                identifier=str(created["identifier"]),
                createdAt=str(created["createdAt"]),
                metadata=cast(Dict[str, Any], created.get("metadata", {})),
            )

    async def delete_feedback(self, feedback_id: str) -> bool:
        with self._lock:
            self._state["feedbacks"].pop(feedback_id, None)
            for thread in self._state["threads"].values():
                for step in thread.get("steps", []):
                    feedback = step.get("feedback")
                    if isinstance(feedback, dict) and feedback.get("id") == feedback_id:
                        step["feedback"] = None
            self._persist()
            return True

    async def upsert_feedback(self, feedback: Feedback) -> str:
        with self._lock:
            feedback_id = feedback.id or str(uuid.uuid4())
            feedback_dict = {
                "forId": feedback.forId,
                "id": feedback_id,
                "value": int(feedback.value),
                "comment": feedback.comment,
            }
            self._state["feedbacks"][feedback_id] = feedback_dict

            for thread in self._state["threads"].values():
                for step in thread.get("steps", []):
                    if step.get("id") == feedback.forId:
                        step["feedback"] = deepcopy(feedback_dict)
            self._persist()
            return feedback_id

    async def create_element(self, element):
        if not getattr(element, "thread_id", None):
            return
        with self._lock:
            thread = self._ensure_thread(str(element.thread_id))
            element_dict = cast(ElementDict, _json_safe(element.to_dict()))
            elements = thread.get("elements", []) or []
            element_id = element_dict.get("id")

            for idx, existing in enumerate(elements):
                if existing.get("id") == element_id:
                    elements[idx] = element_dict
                    break
            else:
                elements.append(element_dict)
            thread["elements"] = elements
            self._persist()

    async def get_element(self, thread_id: str, element_id: str) -> Optional[ElementDict]:
        with self._lock:
            thread = self._state["threads"].get(thread_id)
            if not thread:
                return None
            for element in thread.get("elements", []) or []:
                if element.get("id") == element_id:
                    return cast(ElementDict, deepcopy(element))
            return None

    async def delete_element(self, element_id: str, thread_id: Optional[str] = None):
        with self._lock:
            threads = []
            if thread_id:
                thread = self._state["threads"].get(thread_id)
                if thread:
                    threads.append(thread)
            else:
                threads = list(self._state["threads"].values())

            for thread in threads:
                elements = thread.get("elements", []) or []
                thread["elements"] = [e for e in elements if e.get("id") != element_id]
            self._persist()

    async def create_step(self, step_dict: StepDict):
        thread_id = step_dict.get("threadId")
        if not thread_id:
            return

        with self._lock:
            thread = self._ensure_thread(thread_id)
            step_payload = deepcopy(step_dict)
            if not step_payload.get("createdAt"):
                step_payload["createdAt"] = _now_iso()
            if "metadata" not in step_payload or step_payload["metadata"] is None:
                step_payload["metadata"] = {}
            if "input" not in step_payload:
                step_payload["input"] = ""
            if "output" not in step_payload:
                step_payload["output"] = ""

            self._upsert_step_in_thread(thread, cast(StepDict, step_payload))
            self._persist()

    async def update_step(self, step_dict: StepDict):
        await self.create_step(step_dict)

    async def delete_step(self, step_id: str):
        with self._lock:
            for thread in self._state["threads"].values():
                thread["steps"] = [s for s in thread.get("steps", []) if s.get("id") != step_id]
            self._persist()

    async def get_thread_author(self, thread_id: str) -> str:
        with self._lock:
            thread = self._state["threads"].get(thread_id)
            if not thread or not thread.get("userIdentifier"):
                raise ValueError(f"Author not found for thread_id {thread_id}")
            return str(thread["userIdentifier"])

    async def delete_thread(self, thread_id: str):
        with self._lock:
            self._state["threads"].pop(thread_id, None)
            self._persist()

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        if not filters.userId:
            raise ValueError("userId is required")

        with self._lock:
            threads = [
                cast(ThreadDict, deepcopy(t))
                for t in self._state["threads"].values()
                if t.get("userId") == filters.userId
            ]

        search = (filters.search or "").strip().lower()
        feedback_filter = filters.feedback

        def thread_matches(thread: ThreadDict) -> bool:
            if search:
                in_name = search in str(thread.get("name") or "").lower()
                in_steps = any(
                    search in str(step.get("output") or "").lower()
                    or search in str(step.get("input") or "").lower()
                    for step in thread.get("steps", [])
                )
                if not (in_name or in_steps):
                    return False

            if feedback_filter is not None:
                expected = int(feedback_filter)
                has_match = any(
                    isinstance(step.get("feedback"), dict)
                    and int(step["feedback"].get("value", -1)) == expected
                    for step in thread.get("steps", [])
                )
                if not has_match:
                    return False

            return True

        matched = [t for t in threads if thread_matches(t)]
        matched.sort(key=self._thread_last_updated, reverse=True)

        start_idx = 0
        if pagination.cursor:
            for idx, thread in enumerate(matched):
                if thread["id"] == pagination.cursor:
                    start_idx = idx + 1
                    break

        first = max(1, int(pagination.first))
        page = matched[start_idx : start_idx + first]
        has_next_page = (start_idx + first) < len(matched)

        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=has_next_page,
                startCursor=page[0]["id"] if page else None,
                endCursor=page[-1]["id"] if page else None,
            ),
            data=page,
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        with self._lock:
            thread = self._state["threads"].get(thread_id)
            if not thread:
                return None
            payload = cast(ThreadDict, deepcopy(thread))

        payload["steps"] = sorted(
            payload.get("steps", []),
            key=lambda s: str(s.get("createdAt") or s.get("start") or ""),
        )
        return payload

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        with self._lock:
            thread = self._ensure_thread(thread_id)

            if name is not None:
                thread["name"] = str(name)

            if user_id is not None:
                thread["userId"] = user_id
                thread["userIdentifier"] = self._user_identifier_from_id(user_id)

            if tags is not None:
                thread["tags"] = list(tags)

            if metadata is not None:
                base = cast(Dict[str, Any], thread.get("metadata") or {})
                base.update(cast(Dict[str, Any], _json_safe(metadata)))
                thread["metadata"] = base

            self._persist()

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        return None

    async def get_favorite_steps(self, user_id: str) -> List[StepDict]:
        favorites: List[StepDict] = []
        with self._lock:
            for thread in self._state["threads"].values():
                if thread.get("userId") != user_id:
                    continue
                for step in thread.get("steps", []):
                    metadata = step.get("metadata") or {}
                    if isinstance(metadata, dict) and metadata.get("favorite") is True:
                        favorites.append(cast(StepDict, deepcopy(step)))
        return favorites

