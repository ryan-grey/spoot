#!/usr/bin/env python3
"""Check/apply spoot branding without changing Discord identities or permissions.

Run inside the control runtime with --runtime, or use the existing SSM bot token
locally. Application names are edited separately in Discord's Developer Portal.
No tokens, webhook credentials, or private message bodies are printed.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.request

API = "https://discord.com/api/v10"
MAIN_ID = "1543103695544262656"
OLD = re.compile(r"greybot", re.I)


def call(token, method, path, body=None):
    raw = json.dumps(body).encode() if body is not None else None
    for attempt in range(5):
        req = urllib.request.Request(API + path, data=raw, method=method,
            headers={"Authorization": "Bot " + token, "Content-Type": "application/json",
                     "User-Agent": "spoot/1.0", "X-Audit-Log-Reason": "spoot branding update"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
                return json.loads(data) if data else None
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 4:
                delay = float(json.loads(exc.read()).get("retry_after", 1))
                if delay > 60:
                    raise RuntimeError("Discord requested a longer rate-limit wait; retry later") from None
                time.sleep(delay)
                continue
            raise RuntimeError(f"Discord HTTP {exc.code}: {method} {path}") from None


def replace_label(text):
    return OLD.sub("spoot", text or "").replace("Clips", "clips")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--runtime", action="store_true", help="load main and voice-helper tokens from Config")
    parser.add_argument("--avatar", type=Path,
        default=Path(__file__).resolve().parents[1] / "assets" / "spoot-avatar.png")
    args = parser.parse_args()
    if args.runtime:
        from greybot_control.config import Config
        cfg = Config.from_env()
        tokens = [cfg.bot_token, *cfg.voice_helper_tokens]
    else:
        token = os.environ.get("DISCORD_BOT_TOKEN")
        if not token:
            token = subprocess.run(["aws", "--profile", os.environ.get("AWS_PROFILE", "infra"),
                "--region", "us-east-1", "ssm", "get-parameter", "--name",
                "/greybot/discord/bot_token", "--with-decryption", "--query", "Parameter.Value",
                "--output", "text"], check=True, capture_output=True, text=True).stdout.strip()
        tokens = [token]
    avatar = "data:image/png;base64," + base64.b64encode(args.avatar.read_bytes()).decode()
    for number, token in enumerate(tokens):
        user = call(token, "GET", "/users/@me")
        app = call(token, "GET", "/applications/@me")
        if number == 0 and (user["id"] != MAIN_ID or app["id"] != MAIN_ID):
            raise RuntimeError("Unexpected main application; nothing changed")
        if number and not (OLD.search(user["username"]) or user["username"].startswith("spoot clips ")):
            raise RuntimeError("Unexpected helper identity; nothing changed for this helper")
        name = "spoot" if number == 0 else f"spoot clips {number}"
        description = replace_label(app.get("description", ""))
        if args.apply:
            user = call(token, "PATCH", "/users/@me", {"username": name, "avatar": avatar})
            app = call(token, "PATCH", "/applications/@me", {"icon": avatar, "description": description})
        print(json.dumps({"user": user["id"], "name": user["username"], "avatar": user.get("avatar"),
                          "application_name": app["name"], "application_icon": app.get("icon")}))
        for guild in call(token, "GET", "/users/@me/guilds"):
            base = f'/guilds/{guild["id"]}'
            member = call(token, "GET", base + "/members/" + user["id"])
            if args.apply:
                changes = {"nick": name}
                if member.get("avatar"):
                    changes["avatar"] = avatar
                if OLD.search(member.get("bio") or ""):
                    changes["bio"] = replace_label(member["bio"])
                try:
                    member = call(token, "PATCH", base + "/members/@me", changes)
                except RuntimeError as exc:
                    if "HTTP 403" not in str(exc):
                        raise
                    print(json.dumps({"member_profile_requires_admin": user["id"],
                                      "current_nick": member.get("nick")}))
            print(json.dumps({"guild": guild["name"], "nick": member.get("nick")}))
            if number:
                continue
            for role in call(token, "GET", base + "/roles"):
                if OLD.search(role["name"]) and not role.get("managed"):
                    new_name = replace_label(role["name"])
                    if args.apply:
                        try:
                            call(token, "PATCH", base + "/roles/" + role["id"], {"name": new_name})
                        except RuntimeError as exc:
                            if "HTTP 403" not in str(exc):
                                raise
                            print(json.dumps({"role_requires_admin": role["id"], "name": new_name}))
                            continue
                    print(json.dumps({"role": role["id"], "name": new_name, "applied": args.apply}))
            for channel in call(token, "GET", base + "/channels"):
                changes = {key: replace_label(channel[key]) for key in ("name", "topic")
                           if OLD.search(channel.get(key) or "")}
                if changes:
                    if args.apply:
                        call(token, "PATCH", "/channels/" + channel["id"], changes)
                    print(json.dumps({"channel": channel["id"], "fields": list(changes), "applied": args.apply}))
            for hook in call(token, "GET", base + "/webhooks"):
                if OLD.search(hook.get("name") or ""):
                    if args.apply:
                        call(token, "PATCH", "/webhooks/" + hook["id"],
                             {"name": replace_label(hook["name"]), "avatar": avatar})
                    print(json.dumps({"webhook": hook["id"], "applied": args.apply}))


if __name__ == "__main__":
    main()
