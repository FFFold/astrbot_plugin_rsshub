"""轻量级 WebUI 服务

提供基于 aiohttp 的 RSSHub 订阅管理 Web 界面。
"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from pathlib import Path
from typing import Any

from aiohttp import web

from ..config.config_manager import WebUIConfig
from ..persistence.feed_repository_impl import FeedRepositoryImpl
from ..persistence.subscription_repository_impl import SubscriptionRepositoryImpl
from ..utils import get_logger

logger = get_logger()


class RSSHubWebUI:
    """RSSHub 订阅管理 WebUI 服务"""

    _RATE_LIMIT_MAX = 5
    _RATE_LIMIT_WINDOW = 60.0

    def __init__(
        self,
        config: WebUIConfig,
        sub_repo: SubscriptionRepositoryImpl,
        feed_repo: FeedRepositoryImpl,
        template_path: Path | None = None,
        static_dir: Path | None = None,
        minimal_interval: int = 1,
    ) -> None:
        self._config = config
        self._sub_repo = sub_repo
        self._feed_repo = feed_repo
        self._minimal_interval = max(1, minimal_interval)
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._sessions: dict[str, float] = {}
        self._login_attempts: dict[str, list[float]] = {}
        self._cleanup_task: asyncio.Task | None = None

        self._auth_enabled = config.auth_enabled
        self._password = config.password
        if self._auth_enabled and not self._password:
            self._password = secrets.token_urlsafe(24)
            logger.warning(
                "RSSHub WebUI: auto-generated password is active. "
                "Set 'password' in config to use a known value."
            )

        self._session_timeout = max(60, config.session_timeout)

        if template_path is None:
            # 使用新架构的模板路径
            template_path = Path(__file__).parent / "templates" / "index.html"
        if static_dir is None:
            static_dir = Path(__file__).parent / "static"

        self._template_path = template_path
        self._static_dir = static_dir

    async def start(self) -> None:
        """启动 WebUI 服务"""
        app = web.Application()
        app.add_routes(
            [
                web.get("/", self._handle_index),
                web.post("/api/login", self._handle_login),
                web.get("/api/subscriptions", self._handle_list_subs),
                web.patch("/api/subscriptions/{sub_id}", self._handle_patch_sub),
                web.delete(
                    "/api/subscriptions/{sub_id}", self._handle_delete_sub
                ),
            ]
        )
        if self._static_dir.exists():
            app.router.add_static("/static", str(self._static_dir))

        self._runner = web.AppRunner(app)
        await self._runner.setup()

        host = self._config.host
        port = self._config.port

        self._site = web.TCPSite(self._runner, host=host, port=port)
        await self._site.start()
        self._cleanup_task = asyncio.create_task(self._session_cleanup_loop())
        logger.info("RSSHub WebUI started at http://%s:%s", host, port)

    async def stop(self) -> None:
        """停止 WebUI 服务"""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            self._cleanup_task = None
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    @staticmethod
    def _json_response(
        data: dict[str, Any], status: int = 200
    ) -> web.Response:
        return web.Response(
            text=json.dumps(data, ensure_ascii=False),
            status=status,
            content_type="application/json",
        )

    def _is_authorized(self, request: web.Request) -> bool:
        if not self._auth_enabled:
            return True
        token = request.headers.get("X-RSS-Token", "")
        expires_at = self._sessions.get(token)
        if not expires_at:
            return False
        if time.time() > expires_at:
            self._sessions.pop(token, None)
            return False
        return True

    async def _require_auth(
        self, request: web.Request
    ) -> web.Response | None:
        if self._is_authorized(request):
            return None
        return self._json_response(
            {"ok": False, "error": "unauthorized"}, status=401
        )

    def _check_rate_limit(self, ip: str) -> bool:
        now = time.time()
        attempts = self._login_attempts.get(ip, [])
        attempts = [t for t in attempts if now - t < self._RATE_LIMIT_WINDOW]
        self._login_attempts[ip] = attempts
        return len(attempts) < self._RATE_LIMIT_MAX

    async def _session_cleanup_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(300)
                now = time.time()
                expired = [k for k, v in self._sessions.items() if now > v]
                for k in expired:
                    del self._sessions[k]
                stale_ips = [
                    ip
                    for ip, attempts in self._login_attempts.items()
                    if not attempts
                    or now - attempts[-1] > self._RATE_LIMIT_WINDOW
                ]
                for ip in stale_ips:
                    del self._login_attempts[ip]
        except asyncio.CancelledError:
            pass

    async def _handle_index(self, request: web.Request) -> web.Response:
        if not self._template_path.exists():
            return self._json_response(
                {"ok": False, "error": "template_not_found"}, status=500
            )
        html = self._template_path.read_text(encoding="utf-8")
        return web.Response(text=html, content_type="text/html")

    async def _handle_login(self, request: web.Request) -> web.Response:
        if not self._auth_enabled:
            return self._json_response({"ok": True, "token": "no-auth"})

        ip = request.remote or "unknown"
        if not self._check_rate_limit(ip):
            return self._json_response(
                {"ok": False, "error": "rate_limited"}, status=429
            )

        content_type = request.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return self._json_response(
                {"ok": False, "error": "invalid_content_type"}, status=400
            )

        body = await request.read()
        if not body:
            return self._json_response(
                {"ok": False, "error": "empty_body"}, status=400
            )

        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._json_response(
                {"ok": False, "error": "invalid_json"}, status=400
            )

        password = str(data.get("password", ""))
        if not secrets.compare_digest(password, self._password):
            self._login_attempts.setdefault(ip, []).append(time.time())
            return self._json_response(
                {"ok": False, "error": "invalid_password"},
                status=401,
            )

        token = secrets.token_hex(24)
        self._sessions[token] = time.time() + self._session_timeout
        return self._json_response({"ok": True, "token": token})

    async def _handle_list_subs(self, request: web.Request) -> web.Response:
        unauthorized = await self._require_auth(request)
        if unauthorized:
            return unauthorized

        subs = await self._sub_repo.get_all_active()
        feed_ids = {sub.feed_id for sub in subs}
        feeds: dict[int, Any] = {}
        for feed_id in feed_ids:
            feed = await self._feed_repo.get_by_id(feed_id)
            if feed:
                feeds[feed_id] = feed

        items = []
        for sub in subs:
            feed = feeds.get(sub.feed_id)
            items.append(
                {
                    "id": sub.id,
                    "user_id": sub.user_id,
                    "feed_id": sub.feed_id,
                    "feed_title": feed.title if feed else "",
                    "feed_link": feed.link if feed else "",
                    "target_session": sub.target_session,
                    "interval": sub.interval,
                    "notify": sub.notify,
                    "send_mode": sub.send_mode,
                    "length_limit": sub.length_limit,
                    "link_preview": sub.link_preview,
                    "display_author": sub.display_author,
                    "display_via": sub.display_via,
                    "display_title": sub.display_title,
                    "display_entry_tags": sub.display_entry_tags,
                    "style": sub.style,
                    "display_media": sub.display_media,
                    "tags": sub.tags,
                    "title": sub.title,
                }
            )

        return self._json_response({"ok": True, "items": items})

    async def _handle_patch_sub(self, request: web.Request) -> web.Response:
        unauthorized = await self._require_auth(request)
        if unauthorized:
            return unauthorized

        sub_id_str = request.match_info.get("sub_id", "")
        if not sub_id_str.isdigit():
            return self._json_response(
                {"ok": False, "error": "invalid_sub_id"}, status=400
            )
        sub_id = int(sub_id_str)

        content_type = request.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return self._json_response(
                {"ok": False, "error": "invalid_content_type"}, status=400
            )

        body = await request.read()
        if not body:
            return self._json_response(
                {"ok": False, "error": "empty_body"}, status=400
            )

        try:
            data = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return self._json_response(
                {"ok": False, "error": "invalid_json"}, status=400
            )

        sub = await self._sub_repo.get_by_id(sub_id)
        if not sub:
            return self._json_response(
                {"ok": False, "error": "sub_not_found"},
                status=404,
            )

        patch: dict[str, Any] = {}
        int_keys = {
            "interval",
            "notify",
            "send_mode",
            "length_limit",
            "link_preview",
            "display_author",
            "display_via",
            "display_title",
            "display_entry_tags",
            "style",
            "display_media",
        }
        str_keys = {"target_session", "tags", "title"}

        for key, value in data.items():
            if key in int_keys:
                if value in (None, ""):
                    patch[key] = None if key == "interval" else -100
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    int_value = int(value)
                    if key == "interval" and int_value < self._minimal_interval:
                        return self._json_response(
                            {
                                "ok": False,
                                "error": (
                                    f"interval must be >= "
                                    f"{self._minimal_interval}"
                                ),
                            },
                            status=400,
                        )
                    patch[key] = int_value
                elif isinstance(value, str) and value.isdigit():
                    int_value = int(value)
                    if key == "interval" and int_value < self._minimal_interval:
                        return self._json_response(
                            {
                                "ok": False,
                                "error": (
                                    f"interval must be >= "
                                    f"{self._minimal_interval}"
                                ),
                            },
                            status=400,
                        )
                    patch[key] = int_value
                else:
                    return self._json_response(
                        {"ok": False, "error": f"invalid_value for {key}"},
                        status=400,
                    )
            elif key in str_keys:
                patch[key] = str(value) if value is not None else None

        updated = await self._sub_repo.update_options(
            sub_id, sub.user_id, **patch
        )
        if not updated:
            return self._json_response(
                {"ok": False, "error": "update_failed"},
                status=400,
            )

        return self._json_response({"ok": True})

    async def _handle_delete_sub(self, request: web.Request) -> web.Response:
        unauthorized = await self._require_auth(request)
        if unauthorized:
            return unauthorized

        sub_id_str = request.match_info.get("sub_id", "")
        if not sub_id_str.isdigit():
            return self._json_response(
                {"ok": False, "error": "invalid_sub_id"}, status=400
            )
        sub_id = int(sub_id_str)

        sub = await self._sub_repo.get_by_id(sub_id)
        if not sub:
            return self._json_response(
                {"ok": False, "error": "sub_not_found"},
                status=404,
            )

        await self._sub_repo.delete(sub)
        return self._json_response({"ok": True})
