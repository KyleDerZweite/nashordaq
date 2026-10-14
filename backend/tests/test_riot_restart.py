"""Process restart against a controlled HTTP provider, never live Riot evidence."""

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import threading
from contextlib import asynccontextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import hash_password
from app.models import TrackedPlayer, User

TEST_PASSWORD = "regular fixture password"
TEST_PASSWORD_HASH = hash_password(TEST_PASSWORD)


@pytest.mark.parametrize("initial_key", ["", "controlled-rejected-key"])
async def test_replaced_environment_restart_preserves_accounts_and_game_state(
    tmp_path,
    initial_key,
):
    class ControlledRiot(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get("X-Riot-Token") != "controlled-accepted-key":
                self.send_response(403)
                self.end_headers()
                return
            if "/accounts/by-riot-id/" in self.path:
                payload = {"puuid": "new-player"}
            elif "/entries/by-puuid/" in self.path:
                payload = [
                    {
                        "queueType": "RANKED_SOLO_5x5",
                        "tier": "GOLD",
                        "rank": "I",
                        "leaguePoints": 75,
                        "wins": 10,
                        "losses": 10,
                    }
                ]
            else:
                payload = []
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, *_):
            pass

    provider = ThreadingHTTPServer(("127.0.0.1", 0), ControlledRiot)
    thread = threading.Thread(target=provider.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as address:
        address.bind(("127.0.0.1", 0))
        port = address.getsockname()[1]
    origin = f"http://127.0.0.1:{port}"
    provider_origin = f"http://127.0.0.1:{provider.server_port}"
    database_url = f"sqlite+aiosqlite:///{tmp_path}/instance.db"

    @asynccontextmanager
    async def backend(key, log_name):
        env = dict(
            os.environ,
            NASHORDAQ_RIOT_API_KEY=key,
            NASHORDAQ_DATABASE_URL=database_url,
            NASHORDAQ_PUBLIC_URL=origin,
            NASHORDAQ_RIOT_API_BASE_URL=provider_origin,
            NASHORDAQ_RIOT_API_REGION_URL=provider_origin,
            NASHORDAQ_DEMO_MODE_ENABLED="false",
            NASHORDAQ_PORO_ENABLED="false",
            NASHORDAQ_RIOT_REQUEST_STAGGER_SECONDS="0",
        )
        log_path = tmp_path / log_name
        with log_path.open("w") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                env=env,
                stdout=log,
                stderr=log,
            )
            try:
                async with httpx.AsyncClient(base_url=origin) as probe:
                    for _ in range(200):
                        assert process.poll() is None, "Backend exited during startup"
                        try:
                            if (await probe.get("/health")).status_code == 200:
                                break
                        except httpx.ConnectError:
                            pass
                        await asyncio.sleep(0.05)
                    else:
                        raise AssertionError("Backend did not become healthy")
                yield log_path
            finally:
                process.terminate()
                await asyncio.to_thread(process.wait, 10)

    try:
        async with (
            httpx.AsyncClient(
                base_url=origin, headers={"X-Nashordaq-CSRF": "1"}
            ) as operator,
            httpx.AsyncClient(
                base_url=origin, headers={"X-Nashordaq-CSRF": "1"}
            ) as player,
        ):
            async with backend(initial_key, "initial.log") as log_path:
                token = re.search(
                    r"/setup\?token=([A-Za-z0-9_-]+)", log_path.read_text()
                )[1]
                assert (
                    await operator.post(
                        "/api/auth/setup",
                        json={
                            "token": token,
                            "username": "operator",
                            "password": TEST_PASSWORD,
                        },
                    )
                ).status_code == 201
                assert (await operator.get("/api/admin/system/status")).json()[
                    "riot_status"
                ] == ("unchecked" if initial_key else "missing_key")
                engine = create_async_engine(database_url)
                async with async_sessionmaker(
                    engine, expire_on_commit=False
                )() as session:
                    session.add(
                        User(
                            username="regular",
                            email="regular@test",
                            display_name="Regular",
                            password_hash=TEST_PASSWORD_HASH,
                            balance=1234,
                        )
                    )
                    session.add(
                        TrackedPlayer(
                            game_name="Existing",
                            tag_line="EUW",
                            display_name="Existing",
                            puuid="existing",
                            lp_abs=1500,
                            current_price=40,
                        )
                    )
                    await session.commit()
                await engine.dispose()
                assert (
                    await player.post(
                        "/api/auth/login",
                        json={"username": "regular", "password": TEST_PASSWORD},
                    )
                ).status_code == 200
                assert (
                    await player.post(
                        "/api/user/onboarding",
                        json={"game_name": "New", "tag_line": "EUW"},
                    )
                ).status_code == 503
                operator_id = (await operator.get("/api/user/me")).json()["id"]

            async with backend("controlled-accepted-key", "replaced.log"):
                assert (await operator.get("/api/auth/status")).json()[
                    "setup_required"
                ] is False
                assert (await operator.get("/api/user/me")).json()["id"] == operator_id
                assert len((await operator.get("/api/admin/users")).json()) == 2
                assert (await player.get("/api/user/me")).json()["balance"] == 1234
                for _ in range(100):
                    status = (await player.get("/api/system/status")).json()
                    if status["last_market_update_at"]:
                        break
                    await asyncio.sleep(0.05)
                assert status["riot_status"] == "available"
                assert status["last_market_update_at"] is not None
                existing = (await player.get("/api/market/players")).json()
                assert len(existing) == 1 and existing[0]["game_name"] == "Existing"
                assert existing[0]["current_price"] != 40
                assert (
                    await player.post(
                        "/api/user/onboarding",
                        json={"game_name": "New", "tag_line": "EUW"},
                    )
                ).status_code == 200
                assert len((await player.get("/api/market/players")).json()) == 2
    finally:
        provider.shutdown()
        provider.server_close()
        thread.join()
