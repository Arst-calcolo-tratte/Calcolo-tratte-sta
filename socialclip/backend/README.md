# Backend deployment

This API needs Python 3.12, FFmpeg, and outbound internet access. Deploy the `backend` directory as a Docker service. Set `PORT` (provided by most hosts), `FRONTEND_ORIGINS` to the exact HTTPS origin serving the frontend, `MAX_DOWNLOAD_MB` (default 500), and `JOB_TTL_SECONDS` (default 1800).

Do not expose this API publicly without adding rate limiting, authentication, and an abuse-control layer. This starter implementation uses in-memory job state and is intended for a single small personal instance, not multi-instance production.

The backend accepts only a curated set of social domains and does not authenticate to platforms or circumvent DRM, login walls, private media, or platform restrictions. Social site support may change at any time.