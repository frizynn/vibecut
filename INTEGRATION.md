# Kimu fork — notas técnicas

Fork de [Kimu](https://github.com/trykimu/videoeditor) reconvertido en una **app
local de un solo usuario**: sin login, sin claves de API, transcripción y corte
de silencios locales, y copiloto que usa tu agente CLI (Claude Code / Codex).

Guía de uso para el usuario final: [`LEEME.md`](LEEME.md).

## Cómo se arranca

`./start.sh` (o `./install-app.sh` una vez para tenerlo como app del menú) hace
todo: levanta Postgres + Redis vía Docker, instala dependencias la primera vez,
corre backend + renderer + editor, y abre la ventana. Arranque manual de dev:

```bash
pnpm i && (cd backend && uv sync)
docker compose -f docker-compose.dev.yml -f docker-compose.local.yml up -d
(cd backend && uv run uvicorn main:app --reload --port 3000)   # terminal 1
pnpm dlx tsx app/videorender/videorender.ts                    # terminal 2
pnpm dev                                                        # terminal 3 -> :5173
```

`docker-compose.local.yml` fija Postgres 16 (la `:18` de upstream rompe con el
mount del volumen) y lo mapea a un puerto que no choca con un Postgres existente.

## Qué agrega este fork

### 1. Transcripción y corte de silencios (local, sin API key)

- Transcripción con `faster-whisper` (CPU): `.srt` + `captions` partidos para el timeline.
- Corte de silencios con ffmpeg `silencedetect`: devuelve los segmentos a conservar.
- Código en `backend/media/` (`processing.py`, `routes.py`, `schema.py`).

Endpoints (multipart, **`file`** subido o **`media_url`** http(s); en modo local
no requieren cookie):

| Ruta | Devuelve | Parámetros |
|---|---|---|
| `POST /media/transcribe` | `{ language, duration, segments, captions, srt }` | `file`/`media_url`, `language`, `model_size`, `max_caption_chars` |
| `POST /media/cut-silences` | `{ duration, silences, keep_segments, removed_seconds }` | `file`/`media_url`, `noise_db`, `min_silence_seconds`, `padding_seconds`, `min_keep_seconds` |

El frontend manda la URL remota del clip, o si es local (sin R2) sube los bytes
del blob directo (`appendMediaToForm` en `app/utils/llm-handler.ts`).

### 2. Copiloto pluggable, sin API key (`AI_BACKEND=auto`)

`backend/ai/cli_backends.py` + dispatch en `backend/ai/routes.py`. Autodetecta:
`claude` (suscripción Claude) → `codex` (suscripción ChatGPT) → Gemini (API key).
Gemini quedó opcional: el backend arranca sin ninguna clave.

### 3. Edición en la UI + por chat

- Botones "Transcribir" y "Cortar silencios" sobre el clip seleccionado, e
  inserción de emoji como clip de texto (`app/routes/home.tsx`).
- Tools del copiloto `LLMTranscribe` / `LLMCutSilences` (`backend/ai/schema.py`
  + prompt en `routes.py`; ejecutores en `app/utils/llm-handler.ts` y
  `app/components/chat/ChatBox.tsx`). cut-silences compacta los segmentos
  conservados para que el resultado quede contiguo (sin huecos).

### 4. Modo local sin login (`LOCAL_MODE=true`, default)

Usuario único implícito (`local-user`), sin Google OAuth. Respetado por backend
(`auth/routes.py`) y frontend (`app/utils/auth.server.ts`, `app/hooks/useAuth.ts`).
Para cloud/multiusuario: `LOCAL_MODE=false` + configurar BetterAuth.

## Estado verificado

- [x] Stack levanta (Postgres 16, Redis, FastAPI :3000, editor :5173).
- [x] Arranca sin ninguna API key; modo local sin login (`/projects` 200 sin cookie).
- [x] Detección de silencios y transcripción→SRT correctas (probadas con audio real).
- [x] Copiloto Claude Code / Codex devuelve la acción correcta sin API key (probado).
- [x] Botones de UI + tools del copiloto + emoji (typecheck limpio en archivos nuevos).
- [x] Lanzador `./start.sh` + `./install-app.sh` (abre como app en ventana propia).
- [ ] Binario 100% autocontenido sin Docker (Postgres→SQLite, Redis→in-memory). Pendiente.

## Pendiente: app totalmente autocontenida

Hoy "app" = ventana propia (Chrome `--app`) + lanzador de un comando, con los
servicios locales por detrás (Docker para la DB). Un instalable único sin Docker
requiere migrar Postgres→SQLite y sacar Redis (cola de render en proceso), y
empaquetar con Tauri/Electron. Es el siguiente milestone.
