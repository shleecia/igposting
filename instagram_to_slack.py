#!/usr/bin/env python3
"""Ping Slack whenever a new video or Reel appears on an Instagram account.

Runs on a schedule (see .github/workflows/instagram-to-slack.yml). It checks the
account's most recent posts, compares them with state.json, and sends a Slack
message for each new video. Standard library only, so nothing to install.

Environment variables:
  IG_ACCESS_TOKEN    Instagram API token (Instagram API with Instagram Login)
  SLACK_WEBHOOK_URL  Slack incoming webhook URL
  INCLUDE_CAROUSELS  "true" to also ping for carousels that contain a video
  TEST_LATEST        "true" to post the most recent video right now (testing)
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

GRAPH = "https://graph.instagram.com"
STATE_FILE = Path(os.environ.get("STATE_FILE", "state.json"))
MAX_SEEN = 200  # how many post IDs to remember
BASE_FIELDS = "id,media_type,media_product_type,caption,permalink,timestamp,thumbnail_url,username"


def env_flag(name):
    return os.environ.get(name, "").strip().lower() == "true"


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"Missing required environment variable / secret: {name}")
    return value


def fetch_recent_media(token, include_carousels, limit=25):
    fields = BASE_FIELDS + (",children{media_type}" if include_carousels else "")
    query = urllib.parse.urlencode({"fields": fields, "limit": limit, "access_token": token})
    try:
        with urllib.request.urlopen(f"{GRAPH}/me/media?{query}", timeout=30) as resp:
            return json.load(resp).get("data", [])
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"Instagram API error {e.code}: {body}")


def is_video(media, include_carousels):
    if media.get("media_type") == "VIDEO":  # Reels also come through as VIDEO
        return True
    if include_carousels and media.get("media_type") == "CAROUSEL_ALBUM":
        children = media.get("children", {}).get("data", [])
        return any(c.get("media_type") == "VIDEO" for c in children)
    return False


def slack_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_message(media, with_thumbnail=True):
    kind = "Reel" if media.get("media_product_type") == "REELS" else "video"
    user = media.get("username")
    header = f":clapper: New Instagram {kind}" + (f" from *@{user}*" if user else "")
    text = f"{header}\n<{media['permalink']}|View on Instagram>"

    caption = (media.get("caption") or "").strip()
    if caption:
        if len(caption) > 300:
            caption = caption[:297] + "…"
        text += "\n>" + slack_escape(caption).replace("\n", "\n>")

    section = {"type": "section", "text": {"type": "mrkdwn", "text": text}}
    if with_thumbnail and media.get("thumbnail_url"):
        section["accessory"] = {
            "type": "image",
            "image_url": media["thumbnail_url"],
            "alt_text": "Video thumbnail",
        }
    # "text" is the fallback shown in notifications
    return {"text": f"New Instagram {kind}: {media['permalink']}", "blocks": [section]}


def send_to_slack(webhook, payload):
    req = urllib.request.Request(
        webhook,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def post_to_slack(webhook, media):
    """Returns True on success. Retries without the thumbnail if Slack rejects it."""
    for with_thumbnail in (True, False):
        try:
            send_to_slack(webhook, build_message(media, with_thumbnail))
            return True
        except urllib.error.HTTPError as e:
            print(f"Slack error {e.code}: {e.read().decode(errors='replace')}")
        except urllib.error.URLError as e:
            print(f"Slack request failed: {e.reason}")
    return False


def load_state():
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text())


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def main():
    token = require_env("IG_ACCESS_TOKEN")
    webhook = require_env("SLACK_WEBHOOK_URL")
    include_carousels = env_flag("INCLUDE_CAROUSELS")

    media = fetch_recent_media(token, include_carousels)
    state = load_state()
    first_run = state is None
    if first_run:
        state = {"seen": [], "keepalive": ""}
    seen = set(state["seen"])

    videos = [m for m in media if is_video(m, include_carousels)]
    posted, failed = set(), set()

    if env_flag("TEST_LATEST"):
        if videos:
            ok = post_to_slack(webhook, videos[0])
            print(("Sent" if ok else "FAILED to send") + f" test ping for {videos[0]['permalink']}")
            if ok:
                posted.add(videos[0]["id"])
        else:
            print("Test mode: no videos found in the latest posts.")

    if first_run:
        print(f"First run: remembering {len(media)} existing posts without pinging Slack.")
    else:
        new_videos = [m for m in videos if m["id"] not in seen and m["id"] not in posted]
        for m in reversed(new_videos):  # oldest first, so Slack shows them in order
            if post_to_slack(webhook, m):
                print(f"Pinged Slack for {m['permalink']}")
            else:
                failed.add(m["id"])
        if not new_videos:
            print("No new videos.")

    # Remember everything we've looked at (except failed pings, so they retry next run)
    current_ids = [m["id"] for m in media if m["id"] not in failed]
    older_ids = [i for i in state["seen"] if i not in current_ids]
    state["seen"] = (current_ids + older_ids)[:MAX_SEEN]
    # Changes once a month, so the repo always has recent activity and
    # GitHub never auto-disables the schedule.
    state["keepalive"] = datetime.now(timezone.utc).strftime("%Y-%m")
    save_state(state)

    if failed:
        sys.exit(f"{len(failed)} Slack ping(s) failed; they'll be retried on the next run.")


if __name__ == "__main__":
    main()
