const { app, BrowserWindow, Menu, ipcMain } = require('electron')
const path = require('path')
const fs = require('fs')
const http = require('http')
const { spawn } = require('child_process')

const CONFIG_PATH = path.join(app.getPath('userData'), 'config.json')
const LOCAL_SERVER_PORT = 8765
const LOCAL_SERVER_HEALTH_TIMEOUT_MS = 6000

function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'))
  } catch {
    return {}
  }
}

function saveConfig(config) {
  fs.mkdirSync(path.dirname(CONFIG_PATH), { recursive: true })
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(config, null, 2))
}

// Packaged builds get frontend/dist copied in as an extraResource (see
// package.json "build.extraResources"); in dev we serve straight out of
// the sibling frontend/ checkout so `npm run build:frontend` is enough.
function frontendDistPath() {
  return app.isPackaged
    ? path.join(process.resourcesPath, 'frontend-dist')
    : path.join(__dirname, '..', 'frontend', 'dist')
}

function backendDir() {
  return app.isPackaged ? path.join(process.resourcesPath, 'backend') : path.join(__dirname, '..', 'backend')
}

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
}

// Minimal static file server with SPA fallback (any unmatched path serves
// index.html so React Router's client-side routes work) -- avoids pulling
// in express/serve-handler just for this. Binds to a random free port so
// multiple tills on one dev machine never collide.
function startStaticServer(root) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const reqPath = decodeURIComponent((req.url || '/').split('?')[0])
      const resolved = path.normalize(path.join(root, reqPath))
      if (!resolved.startsWith(root)) {
        res.writeHead(403)
        res.end()
        return
      }
      fs.stat(resolved, (err, stat) => {
        const filePath = !err && stat.isFile() ? resolved : path.join(root, 'index.html')
        fs.readFile(filePath, (readErr, data) => {
          if (readErr) {
            res.writeHead(404)
            res.end('Not found')
            return
          }
          res.writeHead(200, { 'Content-Type': MIME_TYPES[path.extname(filePath)] || 'application/octet-stream' })
          res.end(data)
        })
      })
    })
    server.listen(0, '127.0.0.1', () => resolve(server))
    server.on('error', reject)
  })
}

// Spawns sync_agent's local server (see backend/sync_agent/local_server.py)
// as a child process -- it proxies to the shop's real backend
// (config.backendOrigin) when reachable and falls back to its own synced
// SQLite cache + offline sales queue when it isn't, all on one local port
// the frontend talks to unconditionally. Requires a Python environment
// with backend/sync_agent/requirements.txt installed (see desktop/README.md);
// POS_DESKTOP_PYTHON overrides which interpreter to use.
let syncAgentProcess = null

function startSyncAgent(config) {
  const pythonBin = process.env.POS_DESKTOP_PYTHON || 'python'
  const env = {
    ...process.env,
    PYTHONPATH: backendDir(),
    SYNC_AGENT_SERVER_BASE_URL: config.backendOrigin || '',
    SYNC_AGENT_TERMINAL_API_KEY: config.terminalApiKey || '',
    SYNC_AGENT_DB_PATH: path.join(app.getPath('userData'), 'sync_agent.db'),
    SYNC_AGENT_DB_ENCRYPTION_KEY: config.dbEncryptionKey || '',
    SYNC_AGENT_ALLOW_UNENCRYPTED_STORAGE: config.dbEncryptionKey ? 'false' : 'true',
    SYNC_AGENT_LOCAL_SERVER_PORT: String(LOCAL_SERVER_PORT),
  }
  const proc = spawn(pythonBin, ['-m', 'sync_agent.local_server'], { cwd: backendDir(), env })
  proc.stdout.on('data', (chunk) => console.log(`[sync_agent] ${chunk}`.trim()))
  proc.stderr.on('data', (chunk) => console.error(`[sync_agent] ${chunk}`.trim()))
  proc.on('exit', (code) => console.log(`[sync_agent] exited with code ${code}`))
  syncAgentProcess = proc
  return proc
}

function waitForHealth(url, timeoutMs) {
  const startedAt = Date.now()
  return new Promise((resolve, reject) => {
    const attempt = () => {
      const req = http.get(url, (res) => {
        res.resume()
        if (res.statusCode === 200) resolve()
        else retry()
      })
      req.on('error', retry)
    }
    const retry = () => {
      if (Date.now() - startedAt > timeoutMs) {
        reject(new Error(`local server did not become healthy within ${timeoutMs}ms`))
        return
      }
      setTimeout(attempt, 300)
    }
    attempt()
  })
}

// Prefer the embedded sync_agent local server (proxy + offline fallback);
// if it can't start at all (no Python / deps not installed) or doesn't
// come up in time, fall back to the frontend talking to the configured
// backend directly -- online-only, same as before sync_agent embedding,
// so a till without Python set up still works rather than being stuck.
async function resolveApiBaseUrl(config) {
  const origin = (config.backendOrigin || '').replace(/\/+$/, '')
  try {
    startSyncAgent(config)
    await waitForHealth(`http://127.0.0.1:${LOCAL_SERVER_PORT}/health`, LOCAL_SERVER_HEALTH_TIMEOUT_MS)
    return `http://127.0.0.1:${LOCAL_SERVER_PORT}/api/v1`
  } catch (err) {
    console.error('sync_agent local server unavailable, falling back to a direct (online-only) backend connection:', err)
    return `${origin}/api/v1`
  }
}

let mainWindow = null
let config = loadConfig()

function openSettingsWindow() {
  return new Promise((resolve) => {
    const win = new BrowserWindow({
      width: 560,
      height: 480,
      resizable: false,
      autoHideMenuBar: true,
      webPreferences: {
        preload: path.join(__dirname, 'settings-preload.js'),
        contextIsolation: true,
        additionalArguments: [
          `--pos-current-backend-origin=${config.backendOrigin || ''}`,
          `--pos-current-terminal-api-key=${config.terminalApiKey || ''}`,
          `--pos-current-db-encryption-key=${config.dbEncryptionKey || ''}`,
        ],
      },
    })
    win.loadFile(path.join(__dirname, 'settings.html'))

    const onSave = (_event, data) => {
      config = { ...config, ...data }
      saveConfig(config)
      win.close()
    }
    ipcMain.once('settings:save', onSave)
    win.on('closed', () => {
      ipcMain.removeListener('settings:save', onSave)
      resolve()
    })
  })
}

function buildMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Backend Settings...',
          click: async () => {
            await openSettingsWindow()
            // Config is read once at startup (spawning sync_agent, injecting
            // the frontend's API URL), so a change needs a relaunch to apply.
            app.relaunch()
            app.exit()
          },
        },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'View',
      submenu: [
        {
          label: 'Toggle Kiosk Mode',
          click: () => mainWindow && mainWindow.setKiosk(!mainWindow.isKiosk()),
        },
        { role: 'reload' },
        { role: 'toggleDevTools' },
      ],
    },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

async function createMainWindow(apiBaseUrl) {
  const server = await startStaticServer(frontendDistPath())
  const { port } = server.address()

  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      additionalArguments: [`--pos-api-base-url=${apiBaseUrl}`],
    },
  })
  buildMenu()
  mainWindow.on('closed', () => {
    mainWindow = null
    server.close()
  })
  await mainWindow.loadURL(`http://127.0.0.1:${port}`)
}

app.whenReady().then(async () => {
  if (!config.backendOrigin) {
    await openSettingsWindow()
  }
  const apiBaseUrl = await resolveApiBaseUrl(config)
  await createMainWindow(apiBaseUrl)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow(apiBaseUrl)
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

app.on('before-quit', () => {
  if (syncAgentProcess) syncAgentProcess.kill()
})
