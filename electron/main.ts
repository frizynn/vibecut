import { app, BrowserWindow, utilityProcess } from 'electron'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import http from 'http'
import net from 'net'
import { createRequestHandler } from '@react-router/express'
import express from 'express'
import { createProxyMiddleware } from 'http-proxy-middleware'

const IS_DEV = !app.isPackaged

function resourcePath(...parts: string[]): string {
  return IS_DEV
    ? path.join(__dirname, '..', ...parts)
    : path.join(process.resourcesPath, ...parts)
}

// In the packaged app, node_modules live in extraResources/node_modules
// (copied flat via pnpm install --shamefully-hoist in build-macos.sh).
const RUNTIME_NODE_MODULES = IS_DEV
  ? path.join(__dirname, '..', 'node_modules')
  : path.join(process.resourcesPath, 'node_modules')

const BACKEND_DIR = resourcePath('backend')
const VIDEORENDER_JS = resourcePath('dist', 'videorender.bundle.mjs')
const BUILD_SERVER_JS = resourcePath('build', 'server', 'index.js')
const BUILD_CLIENT_DIR = resourcePath('build', 'client')

const PYTHON_BIN = IS_DEV
  ? 'python3'
  : resourcePath('python', 'bin', 'python3.12')
const FFMPEG_BIN = IS_DEV ? 'ffmpeg' : resourcePath('ffmpeg')
const DB_PATH = path.join(app.getPath('userData'), 'vibecut.db')

let backendProcess: ChildProcess | null = null
let rendererProcess: ReturnType<typeof utilityProcess.fork> | null = null
let frontendServer: http.Server | null = null
let mainWindow: BrowserWindow | null = null

function waitForPort(port: number, timeout = 30000): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeout
    const check = () => {
      const socket = new net.Socket()
      socket.setTimeout(500)
      socket
        .on('connect', () => { socket.destroy(); resolve() })
        .on('error', () => { socket.destroy(); retry() })
        .on('timeout', () => { socket.destroy(); retry() })
        .connect(port, '127.0.0.1')
    }
    const retry = () => {
      if (Date.now() >= deadline) {
        reject(new Error(`Timed out waiting for port ${port}`))
      } else {
        setTimeout(check, 500)
      }
    }
    check()
  })
}

async function startFrontend(): Promise<void> {
  const expressApp = express()

  // Proxy API calls to backend and renderer services
  expressApp.use(
    '/backend',
    createProxyMiddleware({
      target: 'http://127.0.0.1:3000',
      changeOrigin: true,
      pathRewrite: { '^/backend': '' },
    })
  )
  expressApp.use(
    '/renderer',
    createProxyMiddleware({
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
      pathRewrite: { '^/renderer': '' },
    })
  )

  // Serve static assets from the built client bundle
  expressApp.use(express.static(BUILD_CLIENT_DIR))

  // Serve the React Router SSR app for all other requests.
  // Dynamic import is required because the built bundle is ESM.
  const serverBuild = () => import(BUILD_SERVER_JS as string) as Promise<never>
  expressApp.all('*', createRequestHandler({ build: serverBuild }))

  await new Promise<void>((resolve) => {
    frontendServer = expressApp.listen(5173, '127.0.0.1', () => resolve())
  })
}

async function startBackend(): Promise<void> {
  const baseEnv: NodeJS.ProcessEnv = {
    ...process.env,
    LOCAL_MODE: 'true',
    VIBECUT_DB_PATH: DB_PATH,
    BETTER_AUTH_SECRET: 'local-desktop-secret',
    BETTER_AUTH_URL: 'http://localhost:5173',
    FFMPEG_PATH: FFMPEG_BIN,
    NODE_ENV: 'production',
  }

  const env: NodeJS.ProcessEnv = IS_DEV
    ? baseEnv
    : {
        ...baseEnv,
        PYTHONHOME: resourcePath('python'),
        PYTHONPATH: resourcePath('python-site-packages'),
        PATH: `${path.dirname(PYTHON_BIN)}:${process.env.PATH ?? ''}`,
      }

  backendProcess = spawn(
    PYTHON_BIN,
    ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '3000'],
    { cwd: BACKEND_DIR, env, stdio: ['ignore', 'pipe', 'pipe'] }
  )

  backendProcess.stdout?.on('data', (d: Buffer) =>
    console.log('[backend]', d.toString().trimEnd())
  )
  backendProcess.stderr?.on('data', (d: Buffer) =>
    console.error('[backend]', d.toString().trimEnd())
  )
  backendProcess.on('exit', (code) => {
    if (code !== null && code !== 0) {
      console.error(`[backend] exited with code ${code}`)
    }
  })
}

async function startRenderer(): Promise<void> {
  rendererProcess = utilityProcess.fork(VIDEORENDER_JS, [], {
    env: {
      ...process.env,
      PORT: '8000',
      LOCAL_MODE: 'true',
      VIBECUT_DB_PATH: DB_PATH,
      FFMPEG_PATH: FFMPEG_BIN,
      NODE_ENV: 'production',
      // Let Node find better-sqlite3, @remotion/*, etc. in the bundled node_modules
      NODE_PATH: RUNTIME_NODE_MODULES,
    },
    stdio: 'pipe',
  })

  rendererProcess.stdout?.on('data', (d: Buffer) =>
    console.log('[renderer]', d.toString().trimEnd())
  )
  rendererProcess.stderr?.on('data', (d: Buffer) =>
    console.error('[renderer]', d.toString().trimEnd())
  )
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 680,
    title: 'Vibecut',
    webPreferences: {
      preload: path.join(__dirname, '..', 'preload', 'index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  })

  mainWindow.loadURL('http://localhost:5173')

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

async function cleanup(): Promise<void> {
  frontendServer?.close()
  backendProcess?.kill('SIGTERM')
  rendererProcess?.kill()
}

app.whenReady().then(async () => {
  try {
    await startBackend()
    await startRenderer()
    await startFrontend()
    await Promise.all([waitForPort(3000), waitForPort(8000)])
    createWindow()
  } catch (err) {
    console.error('Failed to start services:', err)
    app.quit()
  }
})

app.on('will-quit', () => {
  cleanup().catch(console.error)
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    cleanup().then(() => app.quit()).catch(() => app.quit())
  }
})

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow()
  }
})
