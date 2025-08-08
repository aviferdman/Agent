import asyncio
from collections import deque
from typing import Deque, Dict, List

Message = Dict[str, str]  # {"role": str, "content": str}


class SessionMemory:
    __slots__ = ("messages",)

    def __init__(self):
        self.messages: Deque[Message] = deque()

    def append(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})

    def as_list(self) -> List[Message]:
        return list(self.messages)


class MemoryManager:
    """In-process session memory with simple eviction."""

    def __init__(self, max_messages: int, max_approx_tokens: int):
        self._sessions: Dict[str, SessionMemory] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self.max_messages = max_messages
        self.max_approx_tokens = max_approx_tokens

    def _approx_tokens(self, msgs: List[Message]) -> int:
        return sum(len(m.get("content", "")) for m in msgs) // 4

    def _evict(self, mem: SessionMemory):
        while True:
            msgs = mem.as_list()
            if (
                len(msgs) <= self.max_messages
                and self._approx_tokens(msgs) <= self.max_approx_tokens
            ):
                break
            if msgs:
                mem.messages.popleft()
            else:
                break

    def _get_or_create(self, session_id: str) -> SessionMemory:
        mem = self._sessions.get(session_id)
        if mem is None:
            mem = SessionMemory()
            self._sessions[session_id] = mem
        return mem

    def _lock(self, session_id: str) -> asyncio.Lock:
        lk = self._locks.get(session_id)
        if lk is None:
            lk = asyncio.Lock()
            self._locks[session_id] = lk
        return lk

    async def add_message(self, session_id: str, role: str, content: str):
        async with self._lock(session_id):
            mem = self._get_or_create(session_id)
            mem.append(role, content)
            self._evict(mem)

    async def get_history(self, session_id: str) -> List[Message]:
        async with self._lock(session_id):
            mem = self._sessions.get(session_id)
            return mem.as_list() if mem else []

    async def snapshot(self, session_id: str) -> dict:
        hist = await self.get_history(session_id)
        return {
            "session_id": session_id,
            "messages": hist,
            "approx_tokens": self._approx_tokens(hist),
            "count": len(hist),
            "limits": {
                "max_messages": self.max_messages,
                "max_approx_tokens": self.max_approx_tokens,
            },
        }


class NoOpMemoryManager:
    async def add_message(self, session_id: str, role: str, content: str):
        return None

    async def get_history(self, session_id: str):
        return []

    async def snapshot(self, session_id: str):
        return {"session_id": session_id, "disabled": True}


def build_memory(enabled: bool, max_messages: int, max_tokens: int):
    if not enabled:
        return NoOpMemoryManager()
    return MemoryManager(max_messages, max_tokens)
