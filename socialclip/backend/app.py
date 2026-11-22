import os
import re
import uuid
import time
import shutil
import threading
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl, Field

APP_DIR = Path(__file__).resolve().parent
WORK_DIR = Path(os.getenv("WORK_DIR", "/tmp/socialclip"))
WORK_DIR.mkdir(parents=True, exist_ok=True)
MAX_DOWNLOAD_MB = int(os.getenv("MAX_DOWNLOAD_MB", "500"))
JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "1800"))
GIF_MAX_SECONDS = 20
MAX_CLIP_SECONDS = 900
JOBS = {}
LOCK = threading.Lock()

app = FastAPI(title="SocialClip API", version="1.0.0")
origins = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "*").split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

class ConvertRequest(BaseModel):
    url: HttpUrl
    format: str = Field(pattern="^(mp4|gif|mp3)$")
    quality: str = "best"
    duration: int = Field(default=10, ge=1, le=GIF_MAX_SECONDS)
    width: int = Field(default=480, ge=160, le=640)
    audio_bitrate: int = Field(default=192, ge=64, le=320)
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, gt=0, le=MAX_CLIP_SECONDS)

def validate_source(url: str):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("È consentito solo un URL HTTPS valido.")
    host = parsed.hostname.lower().rstrip(".")
    allowed = (
        host == "youtube.com" or host.endswith(".youtube.com") or host == "youtu.be"
        or host == "instagram.com" or host.endswith(".instagram.com")
        or host == "facebook.com" or host.endswith(".facebook.com") or host == "fb.watch"
        or host == "tiktok.com" or host.endswith(".tiktok.com")
        or host == "vimeo.com" or host.endswith(".vimeo.com")
        or host == "x.com" or host.endswith(".x.com") or host == "twitter.com" or host.endswith(".twitter.com")
        or host == "reddit.com" or host.endswith(".reddit.com")
    )
    if not allowed:
        raise ValueError("Dominio non ancora abilitato. Sono accettati YouTube, Instagram, Facebook, TikTok, Vimeo, X e Reddit.")
    # No credentials, custom ports, IP literals, localhost, or nonstandard URL schemes.
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("URL non valido.")
    if re.match(r"^(\d{1,3}\.){3}\d{1,3}$", host) or host in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Host non consentito.")

def update_job(job_id, **values):
    with LOCK:
        if job_id in JOBS:
            JOBS[job_id].update(values)

def cleanup_expired():
    now = time.time()
    with LOCK:
        expired = [key for key, job in JOBS.items() if now - job["created"] > JOB_TTL_SECONDS]
        for key in expired:
            folder = JOBS[key].get("folder")
            if folder:
                shutil.rmtree(folder, ignore_errors=True)
            JOBS.pop(key, None)

def run_ffmpeg(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=240)
    if result.returncode != 0:
        raise RuntimeError("Conversione FFmpeg non riuscita. Riprova con un video più breve o una qualità inferiore.")

def process_job(job_id, request_data):
    folder = WORK_DIR / job_id
    folder.mkdir(parents=True, exist_ok=True)
    update_job(job_id, folder=str(folder), status="processing", progress=10, message="Lettura delle informazioni video…")
    try:
        fmt = request_data["format"]
        source_template = str(folder / "source.%(ext)s")
        ydl_opts = {
            "outtmpl": source_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 20,
            "retries": 1,
            "fragment_retries": 1,
            "max_filesize": MAX_DOWNLOAD_MB * 1024 * 1024,
            "continuedl": False,
        }
        if fmt == "mp3":
            ydl_opts.update({"format": "bestaudio/best"})
        else:
            if request_data["quality"] == "best":
                ydl_opts.update({"format": "best[height<=1080]/best"})
            else:
                height = int(request_data["quality"])
                ydl_opts.update({"format": f"best[height<={height}]/best"})
        update_job(job_id, progress=18, message="Download del contenuto autorizzato…")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request_data["url"], download=True)
            source_path = Path(ydl.prepare_filename(info))
        if not source_path.exists():
            candidates = [p for p in folder.iterdir() if p.is_file()]
            if not candidates:
                raise RuntimeError("Il file sorgente non è stato creato.")
            source_path = candidates[0]
        if source_path.stat().st_size > MAX_DOWNLOAD_MB * 1024 * 1024:
            raise RuntimeError(f"Il file supera il limite di {MAX_DOWNLOAD_MB} MB.")
        update_job(job_id, progress=72, message="Conversione del formato…")
        start = request_data.get("start")
        end = request_data.get("end")
        clip_args = []
        if start is not None and end is not None:
            if end <= start:
                raise RuntimeError("Intervallo clip non valido.")
            if end - start > MAX_CLIP_SECONDS:
                raise RuntimeError("La clip supera il limite di 15 minuti.")
            clip_args = ["-ss", str(start), "-to", str(end)]
        output_ext = {"mp4": "mp4", "gif": "gif", "mp3": "mp3"}[fmt]
        output_path = folder / f"SocialClip.{output_ext}"
        if fmt == "mp4":
            run_ffmpeg(["ffmpeg", "-y", *clip_args, "-i", str(source_path), "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-c:a", "aac", "-movflags", "+faststart", str(output_path)])
        elif fmt == "mp3":
            run_ffmpeg(["ffmpeg", "-y", *clip_args, "-i", str(source_path), "-vn", "-b:a", f'{request_data["audio_bitrate"]}k', str(output_path)])
        else:
            duration = int(request_data["duration"])
            # A GIF is limited to a short segment. A user clip range takes precedence.
            gif_start = float(start or 0)
            gif_duration = min(GIF_MAX_SECONDS, float(end - start) if start is not None and end is not None else duration)
            width = int(request_data["width"])
            vf = f"fps=12,scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer"
            run_ffmpeg(["ffmpeg", "-y", "-ss", str(gif_start), "-t", str(gif_duration), "-i", str(source_path), "-vf", vf, "-loop", "0", str(output_path)])
        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Il file convertito è vuoto.")
        update_job(job_id, status="done", progress=100, message="File pronto per il download.", filename=output_path.name, output=str(output_path))
    except Exception as exc:
        update_job(job_id, status="error", progress=100, message=str(exc)[:500])
        shutil.rmtree(folder, ignore_errors=True)

@app.get("/api/health")
def health():
    return {"status": "ok"}

@app.post("/api/convert")
def convert(payload: ConvertRequest):
    cleanup_expired()
    url = str(payload.url)
    try:
        validate_source(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    data = payload.model_dump()
    if data["format"] == "gif" and data.get("end") is not None and data.get("start") is None:
        raise HTTPException(status_code=400, detail="Per indicare la fine della clip devi specificare anche l'inizio.")
    job_id = uuid.uuid4().hex
    with LOCK:
        JOBS[job_id] = {
            "created": time.time(), "status": "queued", "progress": 0,
            "message": "Richiesta accettata.", "filename": None, "folder": None, "output": None
        }
    thread = threading.Thread(target=process_job, args=(job_id, data), daemon=True)
    thread.start()
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    cleanup_expired()
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Processo non trovato o scaduto.")
        return {k: job[k] for k in ("status", "progress", "message", "filename")}

@app.get("/api/jobs/{job_id}/download")
def download(job_id: str):
    cleanup_expired()
    with LOCK:
        job = JOBS.get(job_id)
        if not job or job.get("status") != "done" or not job.get("output"):
            raise HTTPException(status_code=404, detail="File non disponibile.")
        path = Path(job["output"])
        name = job["filename"] or "SocialClip"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Il file è stato eliminato.")
    return FileResponse(path, filename=name, media_type="application/octet-stream")
