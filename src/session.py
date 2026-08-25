from collections import defaultdict

MAX_HISTORY_MESSAGES = 12


class SessionManager:
    def __init__(self, max_messages: int = MAX_HISTORY_MESSAGES):
        self.max_messages = max_messages
        self._sessions: dict[str, list[dict]] = defaultdict(list)

    def get_history(self, session_id: str) -> list[dict]:
        return list(self._sessions.get(session_id, []))

    def append(self, session_id: str, role: str, content: str) -> None:
        history = self._sessions[session_id]
        history.append({"role": role, "content": content})
        del history[: -self.max_messages]

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


SESSIONS = SessionManager()
