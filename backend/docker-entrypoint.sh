#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'EOF'
import time
import sys
from sqlalchemy import create_engine
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url)
for attempt in range(30):
    try:
        with engine.connect():
            print("Database is ready.")
            sys.exit(0)
    except Exception:
        time.sleep(1)
print("Database never became ready.", file=sys.stderr)
sys.exit(1)
EOF

if [ "${SKIP_MIGRATIONS:-}" = "true" ]; then
    echo "SKIP_MIGRATIONS=true -- not running migrations or seeding from this container (e.g. the Celery worker, so two processes don't race to migrate/seed the same database on boot)."
else
    echo "Running migrations..."
    alembic upgrade head
    echo "Seeding demo data (no-op if already seeded)..."
    python -m app.seed
fi

exec "$@"
