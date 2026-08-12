"""
ZYROX MODS - Single File YouTube Direct Downloader API
Reverse engineered from v31.www-y2mate.com -> cnv.cx/v2 backend

One file = Full API
- No external DB, no Turnstile, no yt-dlp (uses cnv.cx/v2 backend)
- Direct video/audio download via a streaming proxy (works with plain curl)

Deploy on Render:
  Build : pip install -r requirements.txt
  Start : uvicorn app:app --host 0.0.0.0 --port $PORT

Local run:
  pip install -r requirements.txt
  uvicorn app:app --host 0.0.0.0 --port 8000

Curl examples:
  # JSON link (for your own app / code)
  curl "http://localhost:8000/api/download?url=https://youtu.be/dQw4w9WgXcQ&format=mp4&quality=720"

  # Direct download (streams through this API)
  curl -L "http://localhost:8000/dl?url=https://youtu.be/dQw4w9WgXcQ&format=mp4&quality=720" -o video.mp4

  # MP3
  curl -L "http://localhost:8000/dl?url=https://youtu.be/dQw4w9WgXcQ&format=mp3&quality=320" -o audio.mp3

Author: ZYROX MODS (reverse engineered v31.www-y2mate.com)
"""

import time
import re
import threading
from pathlib import Path

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import requests
import urllib3
urllib3.disable_warnings()

app = FastAPI(title="ZYROX Single File Downloader API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the static frontend (index.html + assets)
_BASE = Path(__file__).resolve().parent
_STATIC = _BASE / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC)), name="static")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BACKEND_ORIGIN = "https://frame.y2meta-uk.com"   # origin/referer sent to cnv.cx
TUNNEL_REFERER = "https://cnv.cx/"               # referer the tunnel requires

YT_REGEX = re.compile(
    r'(?:youtube\.com/(?:watch\?v=|embed/|v/|shorts/)|youtu\.be/)'
    r'([A-Za-z0-9_-]{11})'
)

MP4_QUALITIES = ["144", "240", "360", "480", "720", "1080", "1440", "2160"]
MP3_QUALITIES = ["64", "128", "192", "256", "320"]

# ---------------------------------------------------------------------------
# Sanity-key cache (the cnv.cx key is valid for a while, reuse it to be fast)
# ---------------------------------------------------------------------------
_key_lock = threading.Lock()
_key_cache = {"key": None, "fetched_at": 0.0}
KEY_TTL = 8 * 60  # seconds


def _common_headers():
    return {
        "Origin": BACKEND_ORIGIN,
        "Referer": BACKEND_ORIGIN + "/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def get_cnv_key(video_id: str) -> str:
    """Step 1: get/reuse a sanity key from cnv.cx."""
    now = time.time()
    with _key_lock:
        if _key_cache["key"] and (now - _key_cache["fetched_at"]) < KEY_TTL:
            return _key_cache["key"]

    headers = _common_headers()
    headers["Accept"] = "application/json"
    try:
        r = requests.get(
            f"https://cnv.cx/v2/sanity/key?id={video_id}",
            headers=headers, timeout=15, verify=False,
        )
        r.raise_for_status()
        j = r.json()
        key = j.get("key")
        if not key:
            raise HTTPException(status_code=502, detail="Backend returned no key")
        with _key_lock:
            _key_cache["key"] = key
            _key_cache["fetched_at"] = now
        return key
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to get backend key: {e}")


def _invalidate_key():
    """Force the next get_cnv_key() call to fetch a fresh key."""
    with _key_lock:
        _key_cache["key"] = None
        _key_cache["fetched_at"] = 0.0


def _call_converter(video_id: str, fmt: str, quality: str, key: str):
    """Logic from v31 JS: aqual/vqual are swapped for mp3."""
    if fmt == "mp3":
        aqual = quality   # bitrate, e.g. 320
        vqual = "720"
    else:
        aqual = "128"
        vqual = quality

    form_data = {
        "link": f"https://youtu.be/{video_id}",
        "format": fmt,
        "audioBitrate": aqual,
        "videoQuality": vqual,
        "filenameStyle": "pretty",
        "vCodec": "h264",
    }

    headers = _common_headers()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    headers["Accept"] = "*/*"
    headers["key"] = key

    r = requests.post(
        "https://cnv.cx/v2/converter", data=form_data,
        headers=headers, timeout=40, verify=False,
    )
    return r


def get_direct_link(video_id: str, fmt: str = "mp4", quality: str = "720"):
    """Step 2: ask cnv.cx converter for a tunnel URL.

    If the cached sanity key has expired/rejected by the backend (HTTP 403),
    invalidate the cache and retry once with a fresh key before giving up.
    """
    last_err = None
    for attempt in range(2):
        key = get_cnv_key(video_id)
        try:
            r = _call_converter(video_id, fmt, quality, key)
            if r.status_code == 403 and attempt == 0:
                # stale/expired sanity key -> get a fresh one and retry
                _invalidate_key()
                last_err = f"stale key (HTTP 403), retrying with fresh key"
                continue
            r.raise_for_status()
            j = r.json()
            if "url" not in j:
                raise HTTPException(status_code=502, detail=f"Backend returned no url: {j}")
            return j  # {status, url, filename}
        except HTTPException:
            raise
        except Exception as e:
            last_err = str(e)
            # Any other HTTP error -> also refresh key and try once more
            if attempt == 0:
                _invalidate_key()
                continue

    raise HTTPException(status_code=502, detail=f"Converter failed: {last_err}")


def extract_id(url: str):
    if not url:
        return None
    m = YT_REGEX.search(url)
    if m:
        return m.group(1)
    if re.match(r"^[A-Za-z0-9_-]{11}$", url.strip()):
        return url.strip()
    return None


def validate(fmt: str, quality: str):
    fmt = (fmt or "mp4").lower()
    quality = str(quality or "")
    if fmt == "mp4":
        if quality not in MP4_QUALITIES:
            raise HTTPException(status_code=400,
                detail=f"Invalid mp4 quality '{quality}'. Allowed: {', '.join(MP4_QUALITIES)}")
    elif fmt == "mp3":
        if quality not in MP3_QUALITIES:
            raise HTTPException(status_code=400,
                detail=f"Invalid mp3 bitrate '{quality}'. Allowed: {', '.join(MP3_QUALITIES)}")
    else:
        raise HTTPException(status_code=400, detail="format must be 'mp4' or 'mp3'")
    return fmt, quality


def _safe_filename(name: str) -> str:
    name = re.sub(r'["\\/:*?<>|]', "_", name or "download")
    name = re.sub(r'\s+', " ", name).strip()
    return name or "download"


def _tunnel_stream(url: str):
    """Open a streaming connection to the tunnel URL with the required headers."""
    return requests.get(
        url,
        headers={
            "Referer": TUNNEL_REFERER,
            "Origin": TUNNEL_REFERER.rstrip("/"),
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        },
        stream=True, timeout=40, verify=False,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/", response_class=FileResponse)
def home():
    return FileResponse(str(_STATIC / "index.html"))


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "ZYROX Single File API", "backend": "cnv.cx/v2", "version": "1.0"}


@app.get("/api/download")
def api_download(
    url: str = Query(..., description="YouTube URL or 11-char ID"),
    format: str = Query("mp4", description="mp4 or mp3"),
    quality: str = Query("720", description="mp4: 144..2160 | mp3: 64..320 kbps"),
):
    """Return JSON with the direct tunnel URL. Use this from your own code/app."""
    vid = extract_id(url)
    if not vid:
        raise HTTPException(status_code=400,
            detail="Invalid YouTube URL or ID. Example: https://youtu.be/dQw4w9WgXcQ or dQw4w9WgXcQ")
    fmt, quality = validate(format, quality)
    result = get_direct_link(vid, fmt, quality)
    return JSONResponse({
        "success": True,
        "videoId": vid,
        "format": fmt,
        "quality": quality,
        "filename": result.get("filename"),
        "direct_url": result.get("url"),
        "status": result.get("status"),
        "note": "For the browser use /dl (redirects to CDN). For curl, add a Referer header or use /dl?stream=1.",
        "curl_download": f'curl -L -H "Referer: https://zyroxy.onrender.com/" "{result.get("url")}" -o "out.{fmt}"',
    })


@app.get("/dl")
def direct_download(
    url: str = Query(..., description="YouTube URL or 11-char ID"),
    format: str = Query("mp4"),
    quality: str = Query("720"),
    stream: int = Query(0, description="1 = stream through this server (curl), 0 = redirect to CDN (browser)"),
):
    """Download the file.

    Default (stream=0): 302-redirect straight to the CDN tunnel URL. The browser
    downloads directly at full speed, so large videos finish reliably (no timeout /
    incomplete .temp file). The tunnel accepts our page's origin as Referer, which the
    browser sends automatically.

    stream=1: proxy the bytes through this server (for `curl -L` without a Referer).
    """
    vid = extract_id(url)
    if not vid:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")
    fmt, quality = validate(format, quality)
    result = get_direct_link(vid, fmt, quality)

    tunnel_url = result.get("url")
    if not tunnel_url:
        raise HTTPException(status_code=502, detail="Backend gave no download URL")
    filename = _safe_filename(result.get("filename", f"{vid}.{fmt}"))

    # Default: redirect browser straight to the CDN for a fast, reliable download.
    if stream == 0:
        return RedirectResponse(url=tunnel_url, status_code=302)

    # stream=1: proxy through this server (curl-friendly).
    try:
        upstream = _tunnel_stream(tunnel_url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Tunnel unreachable: {e}")

    if upstream.status_code != 200:
        upstream.close()
        raise HTTPException(status_code=502,
            detail=f"Tunnel refused download (HTTP {upstream.status_code}). It may have expired; retry.")

    content_type = upstream.headers.get("Content-Type", "application/octet-stream")
    content_length = upstream.headers.get("Content-Length")

    def gen():
        try:
            for chunk in upstream.iter_content(chunk_size=256 * 1024):
                if chunk:
                    yield chunk
        finally:
            upstream.close()

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if content_length:
        headers["Content-Length"] = content_length

    return StreamingResponse(
        gen(),
        media_type=content_type,
        headers=headers,
    )


@app.get("/download")
def download_alias(
    url: str = Query(...), format: str = Query("mp4"), quality: str = Query("720"),
):
    """Alias for /dl (redirect to CDN)."""
    return direct_download(url, format, quality)


@app.get("/api/y2mate/v31")
def compat_y2mate(
    videoId: str = Query(...), format: str = Query("mp4"), quality: str = Query("720"),
):
    """Compatibility endpoint, returns the raw tunnel result."""
    fmt, quality = validate(format, quality)
    return get_direct_link(videoId, fmt, quality)
