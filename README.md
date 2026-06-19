<br />

<p align="center">
  <img width="120" src="public/favicon.png" alt="Vibecut" />
</p>

<h1 align="center">Vibecut</h1>

<p align="center">
  Editor de video local con IA — transcripción, corte de silencios y un copiloto
  que usa tu agente (Claude Code / Codex). <strong>Sin login, sin claves de API, sin Docker.</strong>
</p>

<p align="center">
  <a href="LEEME.md">Guía rápida (ES)</a> &nbsp;·&nbsp;
  <a href="INTEGRATION.md">Notas técnicas</a> &nbsp;·&nbsp;
  <a href="https://github.com/frizynn/vibecut">GitHub</a>
</p>

---

## Qué es

Vibecut es un editor de video que corre **entero en tu máquina**. Edita, ponele
subtítulos automáticos, cortá los silencios, agregá emojis — o **hablale a un
copiloto en español** para que haga los cambios por vos.

Pensado para que cualquiera lo use: no hay que crear cuenta, ni conseguir API
keys, ni levantar servicios. Una sola app.

## Features

- 🎬 **Editor completo**: timeline multipista, preview en vivo, transiciones, texto, export.
- 💬 **Subtítulos automáticos**: transcripción local con Whisper → captions en el timeline.
- ✂️ **Corte de silencios** automático (deja el corte contiguo, sin huecos).
- 😀 **Emojis** y textos.
- 🤖 **Copiloto agéntico**: pedile en lenguaje natural ("cortá los silencios y ponele subtítulos").
- 🔒 **Privado y local**: tus videos no salen de tu compu.

## Empezar

Bajá el instalador desde **[Releases](https://github.com/frizynn/vibecut/releases)**
y corré:

```bash
bash install.sh
```

O directamente desde el código:

```bash
git clone https://github.com/frizynn/vibecut
cd vibecut
./install-app.sh    # una vez: lo deja como app del menú
```

Después buscá **"Vibecut"** en el menú de aplicaciones, o corré `./start.sh`.
Se abre en su propia ventana. La primera vez instala las dependencias solo.

**Requisitos** (una vez): [Node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/),
[uv](https://docs.astral.sh/uv/), y **ffmpeg**. No hace falta Docker.

Guía paso a paso en español: **[LEEME.md](LEEME.md)**.

## El copiloto, sin claves de API

El copiloto detecta **automáticamente** qué agente tenés instalado y usa tu
suscripción — no necesita ninguna API key:

1. **Claude Code** (`claude`) → tu suscripción de Claude.
2. si no, **Codex** (`codex`) → tu suscripción de ChatGPT.
3. si no hay ninguno, **Gemini** (con una key gratis opcional).

Configurable con `AI_BACKEND` en `.env` (`auto` por defecto).

## Cómo está hecho

React + React Router (frontend) · FastAPI / Python (motor) · Remotion (render) ·
SQLite en modo local (sin Postgres ni Redis). Detalles en
[INTEGRATION.md](INTEGRATION.md).

## Créditos y licencia

Vibecut es un fork de **[Kimu](https://github.com/trykimu/videoeditor)**, bajo
**GNU AGPL-3.0** (ver [LICENSE](LICENSE.md)). Aplica también la
[licencia de Remotion](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md)
en las partes correspondientes.
