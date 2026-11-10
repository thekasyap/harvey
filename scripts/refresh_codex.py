#!/usr/bin/env python3
"""Auto-refreshes Codex OAuth tokens when older than 4 days, preventing the 8-day expiration pause."""

import json
import os
import shutil
import time
from datetime import datetime, timezone
import httpx

CODEX_AUTH = os.path.expanduser("~/.codex/auth.json")
LOG_FILE = "/opt/harvey/data/codex_refresh.log"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
REFRESH_THRESHOLD_DAYS = 4


def refresh_if_needed():
    if not os.path.exists(CODEX_AUTH):
        return
    try:
        data = json.load(open(CODEX_AUTH))
    except Exception as e:
        print(f"Error reading {CODEX_AUTH}: {e}")
        return

    last_refresh_str = data.get("last_refresh", "")
    last_refresh_ts = 0.0
    if last_refresh_str:
        clean = last_refresh_str.split(".")[0].replace("Z", "+00:00")
        try:
            last_refresh_ts = datetime.fromisoformat(clean).timestamp()
        except Exception:
            pass

    age_days = (time.time() - last_refresh_ts) / 86400.0
    if age_days < REFRESH_THRESHOLD_DAYS:
        print(f"Codex tokens are {age_days:.1f} days old (threshold: {REFRESH_THRESHOLD_DAYS} days). No refresh needed.")
        return

    tokens = data.get("tokens", {})
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("No refresh_token found in auth.json")
        return

    print(f"Refreshing Codex token (age: {age_days:.1f} days)...")
    try:
        resp = httpx.post(
            "https://auth.openai.com/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
    except Exception as e:
        print(f"HTTP error refreshing token: {e}")
        return

    if resp.status_code == 200:
        res = resp.json()
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        new_tokens = {
            "id_token": res["id_token"],
            "access_token": res["access_token"],
            "refresh_token": res.get("refresh_token", refresh_token),
        }
        if "account_id" in tokens:
            new_tokens["account_id"] = tokens["account_id"]
        data["tokens"] = new_tokens
        data["last_refresh"] = now_iso

        shutil.copyfile(CODEX_AUTH, CODEX_AUTH + ".bak")
        with open(CODEX_AUTH, "w") as f:
            json.dump(data, f, indent=2)
        os.chmod(CODEX_AUTH, 0o600)
        log_msg = f"{now_iso} - Successfully refreshed Codex OAuth token (was {age_days:.1f} days old)\n"
        print(log_msg)
        try:
            with open(LOG_FILE, "a") as lf:
                lf.write(log_msg)
        except Exception:
            pass
    else:
        print(f"Failed to refresh token: {resp.status_code} {resp.text[:200]}")


if __name__ == "__main__":
    refresh_if_needed()

