import requests
import json
import logging
import threading

from dataclasses import dataclass
from typing import Callable, Optional, TypeVar

F = TypeVar("F", bound=Callable)

from bojansocial_example_bot.api import BojanBotAPI
from bojansocial_example_bot.worker import WorkerPool

logger = logging.getLogger("bojansocial_py")

@dataclass
class PostEvent:
    type: str
    id: str
    author: str
    content: str
    reply_to: Optional[str] = None

@dataclass
class MentionEvent:
    type: str
    post_id: str
    author_id: str
    content: str
    mentions: list[dict]


class BojanBotClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://bsapi.colourlabs.net/",
        num_workers: int = 4,
        reconnect: bool = True,
        reconnect_delay: float = 5.0,
        reconnect_max_delay: float = 60.0,
    ):
        self._base = base_url.rstrip("/")
        self._reconnect = reconnect
        self._reconnect_delay = reconnect_delay
        self._reconnect_max_delay = reconnect_max_delay
        self._stop = threading.Event()

        self._session = requests.Session()
        self._session.headers["Authorization"] = f"Bot {token}"

        self.api = BojanBotAPI(token, base_url, self._session)
        self._pool = WorkerPool(num_workers)
        self.me: Optional[dict] = None

        self._handlers: dict[str, list[Callable]] = {
            "post": [],
            "reply": [],
            "mention": [],
            "error": [],
            "connect": [],
            "disconnect": [],
        }

    def on(self, event: str) -> Callable[[F], F]:
        def decorator(func: F) -> F:
            self._handlers[event].append(func)
            return func
        return decorator

    def on_post(self, func: F) -> F:
        self._handlers["post"].append(func)
        return func

    def on_reply(self, func: F) -> F:
        self._handlers["reply"].append(func)
        return func

    def on_mention(self, func: F) -> F:
        self._handlers["mention"].append(func)
        return func

    def on_error(self, func: F) -> F:
        self._handlers["error"].append(func)
        return func

    def on_connect(self, func: F) -> F:
        self._handlers["connect"].append(func)
        return func

    def on_disconnect(self, func: F) -> F:
        self._handlers["disconnect"].append(func)
        return func

    def run(
        self,
        keywords: Optional[list[str]] = None,
        authors: Optional[list[str]] = None,
        shard_id: int = 0,
        shard_count: int = 1,
    ):
        """Connect and block. Reconnects automatically unless stopped."""
        params = {"shard_id": shard_id, "shard_count": shard_count}
        if keywords:
            params["keywords"] = ",".join(keywords)
        if authors:
            params["authors"] = ",".join(authors)

        delay = self._reconnect_delay

        while not self._stop.is_set():
            try:
                self._connect(params)
                # clean exit resets backoff
                delay = self._reconnect_delay
            except Exception as e:
                logger.exception("stream error")
                self._emit("error", e)

            if not self._reconnect or self._stop.is_set():
                break

            logger.info(f"reconnecting in {delay:.1f}s...")
            self._stop.wait(delay)

            # exponential backoff capped at reconnect_max_delay
            delay = min(delay * 2, self._reconnect_max_delay)

        self._pool.shutdown()

    def run_async(self, **kwargs) -> threading.Thread:
        """Run in a background thread."""
        t = threading.Thread(target=self.run, kwargs=kwargs, daemon=True)
        t.start()
        return t

    def stop(self):
        self._stop.set()

    def _connect(self, params: dict):
        try:
            self.me = self.api.me()
            logger.info(
                f"logged in to bojanSocial as @{self.me['username']} "
                f"({self.me['id']}) display name: {self.me['display_name']})"
            )
        except Exception as e:
            raise RuntimeError(f"failed to fetch bot profile: {e}") from e

        with self._session.get(
            f"{self._base}/api/bots/stream/posts",
            params=params,
            stream=True,
            timeout=(10, None),  # 10s connect timeout, no read timeout
        ) as resp:
            resp.raise_for_status()
            self._emit("connect")
            logger.info("connected to bojanSocial's bot stream API")

            try:
                self._read_stream(resp)
            finally:
                # guaranteed to fire whether we exit cleanly or via exception
                self._emit("disconnect")

    def _read_stream(self, resp: requests.Response):
        """
        Read SSE from the response. Uses iter_content instead of iter_lines
        to avoid data loss on chunks that don't end with a newline.
        """
        buf = ""
        for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
            if self._stop.is_set():
                return
            if not chunk:
                continue

            buf += chunk

            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.rstrip("\r")

                if not line:
                    continue
                if line.startswith(":"):
                    continue
                if line.startswith("data: "):
                    self._dispatch(line[6:])

    def _dispatch(self, raw: str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"failed to parse SSE payload: {raw!r}")
            return

        event_type = data.get("type")

        if event_type in ("post", "reply"):
            event = PostEvent(
                type=event_type,
                id=data["id"],
                author=data["author"],
                content=data["content"],
                reply_to=data.get("reply_to"),
            )
            self._emit(event_type, event)

        elif event_type == "mention":
            event = MentionEvent(
                type=event_type,
                post_id=data["post_id"],
                author_id=data["author_id"],
                content=data["content"],
                mentions=data.get("mentions", []),
            )
            self._emit("mention", event)

        else:
            logger.debug(f"unhandled event type: {event_type!r}")

    def _emit(self, event: str, *args):
        handlers = self._handlers.get(event, [])
        if not handlers and event == "error":
            logger.error(
                f"unhandled error: {args[0]}",
                exc_info=args[0] if args else None,
            )
            return
        for handler in handlers:
            self._pool.submit(handler, *args)