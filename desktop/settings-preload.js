const { contextBridge, ipcRenderer } = require('electron')

function readArg(name) {
  const prefix = `--${name}=`
  const match = process.argv.find((arg) => arg.startsWith(prefix))
  return match ? match.slice(prefix.length) : undefined
}

contextBridge.exposeInMainWorld('settingsAPI', {
  currentBackendOrigin: readArg('pos-current-backend-origin') || '',
  currentTerminalApiKey: readArg('pos-current-terminal-api-key') || '',
  currentDbEncryptionKey: readArg('pos-current-db-encryption-key') || '',
  save: (data) => ipcRenderer.send('settings:save', data),
})
