# ZYROX MODS — YouTube Downloader (Web + API)

A single-service **web app + downloader API** for YouTube. Reverse-engineered from
`v31.www-y2mate.com` -> `cnv.cx/v2` backend. No yt-dlp, no database, no Turnstile.

- 🌐 **Web UI** at `/` — paste a link, pick MP4/MP3 + quality, download.
- 🔌 **JSON API** at `/api/download` for your own apps.
- ⚡ **Streaming download** at `/dl` that works with plain `curl`.

---

## 📁 Project structure

```
zyrox-api/
├── app.py               # FastAPI app (backend + serves the frontend)
├── static/
│   ├── index.html       # Landing page
│   ├── style.css        # Styles
│   └── app.js           # Frontend logic (calls /api/download + /dl)
├── requirements.txt     # Python deps
├── render.yaml          # Render blueprint (optional)
├── Procfile             # Render/Heroku start command (alternative)
├── .gitignore
└── README.md
```

---

## 🚀 Deploy on Render

### Option A — GitHub (recommended)
1. Push this repo to GitHub (see below).
2. On Render: **New → Web Service** → connect the GitHub repo.
3. Render auto-detects `render.yaml` (or set manually):
   - **Runtime:** Python
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. Add `/api/health` as the **health check path**.
5. Deploy. Your app will be at `https://<your-app>.onrender.com`.

### Option B — Manual upload
Upload the folder (without `.git`) as a zip or connect via any Git host.

> **Important:** start command must use `$PORT`, NOT a hardcoded port.

---

## 🌐 Push to GitHub

```bash
# 1. Create an empty repo on GitHub (no README). e.g. zyrox-downloader

# 2. Run from inside the project folder:
git init
git add -A
git commit -m "ZYROX YouTube downloader: web + API"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/zyrox-downloader.git
git push -u origin main
```

> Use a **Personal Access Token** (classic, `repo` scope) as the password if
> GitHub asks for credentials instead of the password.

---

## 🧪 Run locally

```bash
cd zyrox-api
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open http://localhost:8000 in a browser.

---

## 🔌 API reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/static/*` | GET | Frontend assets |
| `/api/health` | GET | Liveness check |
| `/api/download` | GET | JSON: `direct_url`, `filename`, ... |
| `/dl` | GET | Streams the file (curl-friendly) |
| `/download` | GET | Alias of `/dl` |
| `/api/y2mate/v31` | GET | Compatibility, raw tunnel result |

**Get a JSON link**
```bash
curl "https://YOUR-APP.onrender.com/api/download?url=https://youtu.be/dQw4w9WgXcQ&format=mp4&quality=720"
```

**Download a file (curl)**
```bash
curl -L "https://YOUR-APP.onrender.com/dl?url=https://youtu.be/dQw4w9WgXcQ&format=mp4&quality=720" -o video.mp4
curl -L "https://YOUR-APP.onrender.com/dl?url=https://youtu.be/dQw4w9WgXcQ&format=mp3&quality=320" -o audio.mp3
```

**Qualities**
- MP4: `144, 240, 360, 480, 720, 1080, 1440, 2160`
- MP3: `64, 128, 192, 256, 320` kbps

---

## ⚠️ Important notes
- **Legal:** YouTube ToS prohibit unauthorized downloading. Use only for content you
  own or are allowed to download. Educational use. The author isn't responsible for misuse.
- **Third-party backend:** This relies on the reverse-engineered `cnv.cx/v2` service,
  which can change/break anytime. No uptime guarantee.
- **Free Render plan:** `/dl` streams through your server, so downloads use your
  monthly egress (100 GB on the free plan).
- `verify=False` is used because the backend TLS chain is non-standard.

---

## 🛠 How it works
1. `GET cnv.cx/v2/sanity/key?id=<id>` → sanity key (cached ~8 min).
2. `POST cnv.cx/v2/converter` → signed **tunnel URL** on `*.yt-dl.click`.
3. The tunnel needs a `Referer` header, so `/dl` **proxies** the file through the
   server instead of a 302-redirect (a redirect would get a 403).
