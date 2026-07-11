"""Offline-first sync agent for a POS terminal.

Deliberately independent of `app.*` (the FastAPI/Postgres backend
package): this runs on the till itself, potentially on a machine that
never has Postgres or FastAPI installed, and only ever talks to the
server over HTTP through the `SyncTransport` interface in
`sync_agent.domain.transport`. See ARCHITECTURE.md for the full design.
"""
