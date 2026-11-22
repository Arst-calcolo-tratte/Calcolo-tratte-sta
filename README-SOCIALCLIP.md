# SocialClip — design and deployment

This folder contains the SocialClip web app. It is designed for videos that the user owns, has permission to download, or may otherwise lawfully save. It does not bypass DRM, login walls, private content, or platform controls.

## Architecture
- Frontend: static HTML/CSS/JS (can be hosted on GitHub Pages or Cloudflare Pages).
- Backend: FastAPI + yt-dlp + FFmpeg (must run on a container/server; static hosting alone cannot perform extraction/conversion).
- Supported outputs: MP4, MP3, GIF.
- GIF duration is limited to 20 seconds to control resource use. Video downloads have a configurable size cap.
- Processing output is temporary and automatically deleted.

## Backend local run

```bash
cd socialclip/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Install FFmpeg on the server. Set `FRONTEND_ORIGINS`, `MAX_DOWNLOAD_MB`, and `JOB_TTL_SECONDS` environment variables.

## Frontend
Serve `socialclip/frontend` using any static web host. In `app.js`, set `API_BASE` to the backend HTTPS URL.

## Limitations
Social platforms change their access policies and page formats. No tool can guarantee extraction from every arbitrary URL. Private, login-protected, DRM-protected, geo-restricted, or otherwise inaccessible content is not supported. Use platform-provided export/download functions where required.
