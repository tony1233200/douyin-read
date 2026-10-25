#!/usr/bin/env python3
"""douyin-read: resolve a Douyin share link, download its media, transcribe it.

Usage:
    python douyin_read.py <share link or share text> [output dir] [--no-transcribe]

The output directory defaults to ./output/<aweme_id>/ and contains:
    meta.json       title / author / timing info
    video-<id>.mp4  the video (for video posts)
    img-<id>-N.jpg  images (for image posts)
    transcript.txt  speech-to-text result (unless --no-transcribe)

How parsing works:
    Douyin does not offer a public API for share links, so this tool relies on
    third-party public parsing endpoints (see PARSE_ENDPOINTS below). Several
    endpoints are listed; they are tried in order until one returns media
    URLs. These endpoints are run by third parties, may change or go offline
    at any time, and can be replaced by editing the list in this file.
    No account, cookie, or login is required by this tool itself.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Third-party public parsing endpoints (GET, the share URL is passed as the
# "url" query parameter). They are community-run services; availability and
# response formats vary. Add/remove entries freely. "{url}" is replaced with
# the URL-encoded share link.
# ---------------------------------------------------------------------------
PARSE_ENDPOINTS = [
    "https://api.bugpk.com/api/douyin?url={url}",
    "https://api.qsy.ink/api/douyin?url={url}",
]

URL_RE = re.compile(r"https?://[^\s　]+")
VIDEO_HINTS = ("play_addr", "download_addr", "video_url", "play_url")
IMAGE_HINTS = ("images", "image_list", "image_urls")


def extract_url(text: str) -> str:
    """Pull the first URL out of a pasted share text, or return it as-is."""
    m = URL_RE.search(text)
    return m.group(0) if m else text.strip()


def fetch_json(endpoint: str, share_url: str) -> dict:
    import httpx

    url = endpoint.replace("{url}", urllib.parse.quote(share_url, safe=""))
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        r = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return r.json()


def walk(obj, key_pred):
    """Yield values whose key matches key_pred, depth-first."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if key_pred(k):
                yield v
            yield from walk(v, key_pred)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item, key_pred)


def first_str(*values):
    for v in values:
        if isinstance(v, str) and v:
            return v
    return ""


def pick_media(data: dict) -> dict:
    """Extract aweme_id / desc / author / video URL / image URLs from a
    parsing-endpoint response. Endpoint schemas differ, so extraction is
    schema-tolerant: known field names first, then a generic URL scan."""
    detail = data.get("data") if isinstance(data.get("data"), dict) else data

    aweme_id = first_str(detail.get("aweme_id"), detail.get("id"),
                         detail.get("item_id"))
    desc = first_str(detail.get("desc"), detail.get("title"))
    author_obj = detail.get("author") or {}
    author = first_str(
        author_obj.get("nickname") if isinstance(author_obj, dict) else "",
        detail.get("author_name"))

    video_url = ""
    for v in walk(detail, lambda k: k in VIDEO_HINTS):
        if isinstance(v, str) and v.startswith("http"):
            video_url = v
            break
        if isinstance(v, dict):
            lst = v.get("url_list") or []
            if lst:
                video_url = lst[0]
                break
        if isinstance(v, list) and v and isinstance(v[0], str):
            video_url = v[0]
            break
    if not video_url:  # generic fallback: first .mp4-looking URL anywhere
        for v in walk(detail, lambda k: True):
            if isinstance(v, str) and ".mp4" in v and v.startswith("http"):
                video_url = v
                break
    if video_url:
        # "playwm" URLs carry a watermark; "play" is the clean variant.
        video_url = video_url.replace("playwm", "play")

    images = []
    for v in walk(detail, lambda k: k in IMAGE_HINTS):
        if isinstance(v, list):
            for item in v:
                if isinstance(item, str) and item.startswith("http"):
                    images.append(item)
                elif isinstance(item, dict):
                    lst = item.get("url_list") or []
                    if lst:
                        images.append(lst[0])
    # De-duplicate, keep order.
    images = list(dict.fromkeys(images))

    return {"aweme_id": aweme_id or "unknown", "desc": desc,
            "author": author, "video_url": video_url, "images": images}


def parse(share_url: str) -> dict:
    errors = []
    for endpoint in PARSE_ENDPOINTS:
        try:
            data = fetch_json(endpoint, share_url)
            media = pick_media(data)
            if media["video_url"] or media["images"]:
                media["endpoint"] = endpoint.split("?")[0]
                return media
            errors.append(f"{endpoint}: no media in response")
        except Exception as e:  # try the next endpoint
            errors.append(f"{endpoint}: {type(e).__name__}: {str(e)[:120]}")
    raise RuntimeError("All parsing endpoints failed:\n  " + "\n  ".join(errors))


def download(url: str, dest: str) -> None:
    import httpx

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/130.0.0.0 Safari/537.36",
        "Referer": "https://www.douyin.com/",
    }
    with httpx.stream("GET", url, headers=headers,
                      follow_redirects=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes(1 << 16):
                f.write(chunk)


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_transcribe = "--no-transcribe" not in sys.argv
    if not args:
        print(__doc__)
        return 2
    share_url = extract_url(args[0])
    timings = {}

    t0 = time.time()
    try:
        media = parse(share_url)
    except Exception as e:
        print(f"Parsing failed: {e}")
        return 3
    timings["parse_sec"] = round(time.time() - t0, 1)

    aweme_id = media["aweme_id"]
    outdir = args[1] if len(args) > 1 else os.path.join(
        BASE, "output", aweme_id)
    os.makedirs(outdir, exist_ok=True)

    saved = {}
    if media["video_url"]:
        video_path = os.path.join(outdir, f"video-{aweme_id}.mp4")
        t0 = time.time()
        download(media["video_url"], video_path)
        timings["download_sec"] = round(time.time() - t0, 1)
        saved["video"] = os.path.basename(video_path)

        if do_transcribe:
            transcript = os.path.join(outdir, "transcript.txt")
            t0 = time.time()
            subprocess.run(
                [sys.executable, os.path.join(BASE, "transcribe.py"),
                 video_path, transcript],
                check=True,
            )
            timings["transcribe_wall_sec"] = round(time.time() - t0, 1)
            saved["transcript"] = os.path.basename(transcript)

    for i, img_url in enumerate(media["images"], 1):
        img_path = os.path.join(outdir, f"img-{aweme_id}-{i}.jpg")
        download(img_url, img_path)
    if media["images"]:
        saved["images"] = len(media["images"])

    meta = {
        "aweme_id": aweme_id,
        "author": media["author"],
        "desc": media["desc"],
        "source_url": share_url,
        "parse_endpoint": media.get("endpoint", ""),
        "files": saved,
        "timings": timings,
    }
    with open(os.path.join(outdir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
