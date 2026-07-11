from __future__ import annotations

import argparse
import dataclasses
import json
import time

from sync_agent.app import SyncAgentApp, build_app
from sync_agent.config import SyncAgentConfig


def cmd_register(app: SyncAgentApp, args: argparse.Namespace) -> None:
    auth_token = args.auth_token or input("Manager/admin JWT (paste from login): ").strip()
    result = app.transport.register(
        app.config.branch_id, app.config.terminal_name, app.config.device_fingerprint, auth_token
    )
    app.terminal_meta.set("terminal_id", result["id"])
    app.terminal_meta.set("api_key", result["api_key"])
    app.terminal_meta.set("branch_id", result["branch_id"])
    print(f"Registered terminal {result['id']} ({result['name']}).")
    print("Set SYNC_AGENT_TERMINAL_API_KEY to this value for subsequent runs:")
    print(result["api_key"])


def cmd_run(app: SyncAgentApp, args: argparse.Namespace) -> None:
    app.worker.start()
    print(f"Sync worker started (interval={app.config.sync_interval_seconds}s). Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        app.worker.stop()


def cmd_status(app: SyncAgentApp, args: argparse.Namespace) -> None:
    snapshot = app.status_service.snapshot()
    print(json.dumps(dataclasses.asdict(snapshot), indent=2))


def cmd_force_sync(app: SyncAgentApp, args: argparse.Namespace) -> None:
    push_summary = app.sync_service.push_pending()
    pull_summaries = app.sync_service.pull_all()
    print("push:", dataclasses.asdict(push_summary))
    print("pull:", [dataclasses.asdict(s) for s in pull_summaries])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sync_agent")
    sub = parser.add_subparsers(dest="command", required=True)

    register_p = sub.add_parser("register", help="Register this terminal with the server (one-time)")
    register_p.add_argument("--auth-token", default=None, help="Manager/admin JWT; prompted for if omitted")

    sub.add_parser("run", help="Start the background sync worker and block until Ctrl+C")
    sub.add_parser("status", help="Print the local sync status snapshot as JSON")
    sub.add_parser("force-sync", help="Run one push+pull cycle immediately and exit")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    config = SyncAgentConfig.from_env()
    app = build_app(config)
    try:
        {
            "register": cmd_register,
            "run": cmd_run,
            "status": cmd_status,
            "force-sync": cmd_force_sync,
        }[args.command](app, args)
    finally:
        app.close()


if __name__ == "__main__":
    main()
