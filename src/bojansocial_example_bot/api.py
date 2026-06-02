import requests

class BojanBotAPI:
    """synchronous API wrapper. all methods block until the request completes"""

    def __init__(self, token: str, base_url: str, session: requests.Session):
        self._base = base_url.rstrip("/")
        self._session = session

    def _get(self, path: str, **kwargs):
        resp = self._session.get(f"{self._base}{path}", **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: dict, **kwargs):
        resp = self._session.post(f"{self._base}{path}", json=body, **kwargs)
        resp.raise_for_status()
        return resp.json()
    
    def me(self) -> dict:
        return self._get("/api/users/me")

    def post(self, content: str) -> dict:
        return self._post("/api/posts/create", {"content": content})

    def reply(self, content: str, reply_to: str) -> dict:
        return self._post(f"/api/posts/{reply_to}/reply", {"content": content})

    def get_user_data(self, user_id: str) -> dict:
        return self._get(f"/api/users/{user_id}")
    
    def get_user_profile_data(self, user_id: str) -> dict:
        return self._get(f"/api/users/{user_id}/profile")
