# Vibecut — editor de video con IA (local)

Editor de video que corre en tu compu. **Sin login, sin claves de API, sin nada
que configurar.** Editás, le ponés subtítulos automáticos, cortás los silencios,
agregás emojis, y le podés hablar a un copiloto en español para que haga los
cambios por vos.

## Cómo abrirla

**Opción fácil (como una app):**

```bash
./install-app.sh      # una sola vez
```

Después buscá **"Vibecut"** en el menú de aplicaciones y abrila como cualquier
programa. Se abre en su propia ventana.

**Opción terminal:**

```bash
./start.sh
```

La primera vez instala todo solo (tarda un poco). Las siguientes arranca en
segundos y abre la ventana de la app. Para cerrar: cerrá la terminal o Ctrl-C.

## Qué necesitás tener instalado (una vez)

- [Node.js](https://nodejs.org/) + [pnpm](https://pnpm.io/installation)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (para el motor en Python)
- **ffmpeg** (`sudo apt install ffmpeg` en Ubuntu) — para transcripción y silencios.

> No necesitás Docker: en modo local la base de datos es un archivo (SQLite) y no
> hay servicios externos. (Docker solo hace falta si lo desplegás en la nube con
> `LOCAL_MODE=false`.)

## Qué puede hacer

- ✂️ **Cortar silencios** automáticamente (botón o pedíselo al copiloto).
- 💬 **Subtítulos automáticos**: transcribe la voz y pone los textos en la línea de tiempo.
- 😀 **Emojis** y textos.
- 🎬 Cortes, transiciones, multipista, preview en vivo, exportar.
- 🤖 **Copiloto en español**: escribile "cortá los silencios y ponele subtítulos".

## El copiloto: sin claves de API

El copiloto usa automáticamente el agente que tengas instalado y logueado:

1. **Claude Code** (`claude`) — usa tu suscripción de Claude.
2. Si no, **Codex** (`codex`) — usa tu suscripción de ChatGPT.
3. Si no hay ninguno, usa **Gemini** (necesita una clave gratis en `.env`).

No tenés que elegir nada: lo detecta solo. Para que ande con tu suscripción,
asegurate de haber hecho `claude` (login) o `codex login` una vez.

---

¿Detalles técnicos, cómo está armado o cómo contribuir? Mirá
[`INTEGRATION.md`](INTEGRATION.md).
