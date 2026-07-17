const { contextBridge } = require('electron')

// main.js passes the configured backend URL in via additionalArguments
// (see createMainWindow) rather than IPC, since it's needed synchronously
// before the page's own scripts (frontend/src/api/client.ts) run.
function readArg(name) {
  const prefix = `--${name}=`
  const match = process.argv.find((arg) => arg.startsWith(prefix))
  return match ? match.slice(prefix.length) : undefined
}

contextBridge.exposeInMainWorld('__POS_DESKTOP__', {
  apiBaseUrl: readArg('pos-api-base-url') || undefined,
})
