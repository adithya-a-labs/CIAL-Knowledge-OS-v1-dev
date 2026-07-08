"""Database readiness checks that never block API startup."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import text

from backend.app.db.session import SessionLocal, get_database_url


@dataclass(frozen=True)
class DatabaseHealth:
    database_ready: bool
    database_configured: bool
    database_message: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def check_database_health() -> DatabaseHealth:
    database_url = get_database_url()
    if not database_url or SessionLocal is None:
        return DatabaseHealth(
            database_ready=False,
            database_configured=False,
            database_message="DATABASE_URL is not configured; metadata database is disabled.",
        )

    try:
        with SessionLocal() as session:
            session.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001 - health must report, not crash.
        return DatabaseHealth(
            database_ready=False,
            database_configured=True,
            database_message=f"Metadata database is unavailable: {exc}",
        )

    return DatabaseHealth(
        database_ready=True,
        database_configured=True,
        database_message="Metadata database is available.",
    )

