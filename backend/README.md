# Vibecut — backend

Motor en FastAPI (Python 3.12): proyectos, assets, transcripción local
(faster-whisper), corte de silencios (ffmpeg) y el copiloto Vibe.

En modo local usa SQLite y no requiere Postgres ni Redis.

## Setup

```bash
uv sync
uv run pre-commit install   # opcional (hooks de lint)
```

## Correr

```bash
LOCAL_MODE=true uv run uvicorn main:app --reload --port 3000
```

Normalmente no lo corrés a mano: `./start.sh` (en la raíz) levanta backend +
renderer + frontend juntos. Detalles en [../INTEGRATION.md](../INTEGRATION.md).
