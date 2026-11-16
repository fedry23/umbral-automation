#!/usr/bin/env python3
"""Instagram Reel publisher via Instagram Graph API (Python stdlib only)."""

import os
import json
import time
import urllib.request
import urllib.error
import urllib.parse

# ---------------------------------------------------------------------------
# Configuration – read exclusively from environment variables (no hardcoding)
# ---------------------------------------------------------------------------

IG_USER_ID: str = os.environ["IG_USER_ID"]
IG_ACCESS_TOKEN: str = os.environ["IG_ACCESS_TOKEN"]
REEL_VIDEO_URL: str = os.environ["REEL_VIDEO_URL"]
REEL_CAPTION: str = os.environ.get("REEL_CAPTION", "")
IG_PUBLISH_DRY_RUN: str = os.environ.get("IG_PUBLISH_DRY_RUN", "true").lower()

API_BASE = "https://graph.instagram.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _raise_unless(status_code: int, expected: int, msg: str) -> None:
    """Raise an exception unless the HTTP status matches *expected*."""
    if status_code != expected:
        raise RuntimeError(f"{msg} – unexpected status {status_code}")


def _check_https(url: str) -> str:
    """Validate that the provided URL uses HTTPS; raise otherwise."""
    if not url.lower().startswith("https://"):
        raise ValueError(f"REEL_VIDEO_URL must use HTTPS, got: {url}")
    return url


def _post(path: str, data: dict) -> dict:
    """Send a POST request to the Instagram Graph API and return the JSON body."""
    url = f"{API_BASE}{path}"
    body = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req) as resp:
            _raise_unless(resp.status, 200, f"POST {path}")
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST {path} failed ({exc.code}): {body_text}") from exc


def _get(path: str) -> dict:
    """Send a GET request and return the JSON body."""
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            _raise_unless(resp.status, 200, f"GET {path}")
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {path} failed ({exc.code}): {body_text}") from exc


# ---------------------------------------------------------------------------
# Core workflow
# ---------------------------------------------------------------------------


def publish_reel(
    ig_user_id: str = IG_USER_ID,
    ig_access_token: str = IG_ACCESS_TOKEN,
    reel_video_url: str = REEL_VIDEO_URL,
    reel_caption: str = REEL_CAPTION,
) -> dict | None:
    """Create and publish an Instagram Reel.

    Returns the media_publish response dict on success, or *None* when in
    dry-run mode.  Raises on any error so the caller never silently publishes.
    """
    # --- Validate --------------------------------------------------------
    reel_video_url = _check_https(reel_video_url)

    dry_run = os.environ.get("IG_PUBLISH_DRY_RUN", "true").lower() != "false"

    if dry_run:
        print("[DRY-RUN] Skipping publication. "
              "Set IG_PUBLISH_DRY_RUN=false to actually publish.")
        print(f"  IG_USER_ID : {ig_user_id}")
        print(f"  VIDEO_URL  : {reel_video_url}")
        print(f"  CAPTION    : {reel_caption or '(none)'}")
        return None

    # --- 1. Create media container ---------------------------------------
    print("Creating media container…")
    create_resp = _post(
        f"/{ig_user_id}/media",
        {
            "media_type": "REELS",
            "video_url": reel_video_url,
            "caption": reel_caption,
            "access_token": ig_access_token,
        },
    )
    creation_id = create_resp.get("id")
    if not creation_id:
        raise RuntimeError("Creation response missing 'id' field.")
    print(f"  Media container created: {creation_id}")

    # --- 2. Poll until processing finishes -------------------------------
 max_attempts = 60          # ~5 minutes with 5s sleep
 sleep_interval = 5
    print(f"Polling status (up to {max_attempts} attempts)…")
    for attempt in range(1, max_attempts + 1):
 status_resp = _get(
            f"/{creation_id}?fields=status_code,processing_status"
        )
 status_code = status_resp.get("status_code", "UNKNOWN")
 processing = status_resp.get("processing_status", "UNKNOWN")
        print(f"  [{attempt:>3}] status_code={status_code}  "
              f"processing_status={processing}")
        if status_code == "FINISHED":
            print("  Media processing complete.")
            break
        if processing == "FAILED":
            raise RuntimeError(
                f"Media processing failed: {json.dumps(status_resp)}"
            )
        if attempt == max_attempts:
            raise RuntimeError(
                f"Timed out after {max_attempts} attempts "
                f"({max_attempts * sleep_interval}s). "
                f"Final status: {status_code}"
            )
 time.sleep(sleep_interval)

    # --- 3. Publish the reel ---------------------------------------------
    print("Publishing reel…")
 publish_resp = _post(
        f"/{ig_user_id}/media_publish",
        {
            "creation_id": creation_id,
            "access_token": ig_access_token,
        },
    )
    print(f"  Published! ID: {publish_resp.get('id', 'N/A')}")
    return publish_resp


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
 result = publish_reel()
        if result is not None:
            print("\nDone.")
        else:
            print("\n[DRY-RUN] Nothing was published.")
    except Exception as exc:
        print(f"\nERROR: {exc}", flush=True)
        raise
