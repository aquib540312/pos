# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for building sync_agent into standalone binaries so a
POS till needs no Python installed.

Build from the repository root backend/ directory:
    python -m PyInstaller --clean --noconfirm --distpath dist --workpath build/pyinstaller sync_agent/pyinstaller.spec

Output lands in backend/dist/ as two one-dir bundles (one-dir layout keeps
the sqlcipher3 native extension and httpx bundle beside each executable):

- backend/dist/sync_agent_server/ -- the embedded local server (proxy +
  offline fallback) that desktop/main.js spawns as the shell's data layer.
- backend/dist/sync_agent_cli/     -- the one-time `register` / `run` /
  `status` / `force-sync` CLI, so a manager can set a till up with no
  Python on it either.

electron-builder copies those folders into the installer as resources
(see desktop/package.json "build.extraResources") and desktop/main.js
spawns the server binary directly when the app is packaged.

The spec lives inside the sync_agent package on purpose: PyInstaller adds
the entry script's directory to its search path first, and local_server.py
imports sibling modules as `sync_agent.app` etc., so the script's parent
(backend/) must be findable -- SPECPATH resolution below makes that exact
regardless of where PyInstaller is invoked from.
"""

import os

block_cipher = None

# SPECPATH is the directory containing this file (backend/sync_agent).
sync_agent_dir = SPECPATH
backend_dir = os.path.dirname(sync_agent_dir)

_SERVER_ENTRY = os.path.join(sync_agent_dir, "local_server.py")
_CLI_ENTRY = os.path.join(sync_agent_dir, "cli.py")


def _analysis(entry, name):
    return Analysis(
        [entry],
        pathex=[sync_agent_dir, backend_dir],
        binaries=[],
        datas=[],
        hiddenimports=["sqlcipher3", "sqlcipher3.dbapi2"],
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=["tkinter", "unittest", "pydoc", "pdb", "pkg_resources"],
        noarchive=False,
        optimize=0,
    )


def _pyz(analysis):
    return PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)


def _collect(exe, analysis, name):
    return COLLECT(
        exe,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=name,
    )


# -- Local server ----------------------------------------------------------
server_a = _analysis(_SERVER_ENTRY, "sync_agent_server")
server_pyz = _pyz(server_a)
server_exe = EXE(
    server_pyz,
    server_a.scripts,
    [],
    exclude_binaries=True,
    name="sync_agent_server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # keep stdout/stderr so desktop/main.js can log sync_agent output
    disable_windowed_traceback=False,
)
server_coll = _collect(server_exe, server_a, "sync_agent_server")

# -- CLI -------------------------------------------------------------------
cli_a = _analysis(_CLI_ENTRY, "sync_agent_cli")
cli_pyz = _pyz(cli_a)
cli_exe = EXE(
    cli_pyz,
    cli_a.scripts,
    [],
    exclude_binaries=True,
    name="sync_agent_cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)
cli_coll = _collect(cli_exe, cli_a, "sync_agent_cli")