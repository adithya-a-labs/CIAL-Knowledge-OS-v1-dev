"""continuous indexing queue, leases, workers, and generations

Revision ID: 20260724_0016
Revises: 20260724_0015
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260724_0016"
down_revision = "20260724_0015"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB()
ACTIVE = (
    "'pending','claimed','extracting','chunked','embedding','writing',"
    "'verifying','retry_wait'"
)


def upgrade() -> None:
    op.drop_constraint("ck_indexing_jobs_status", "indexing_jobs", type_="check")
    op.execute("DROP INDEX IF EXISTS uq_indexing_jobs_active_document_version")

    op.add_column("indexing_jobs", sa.Column("asset_type", sa.Text(), server_default="document", nullable=False))
    op.add_column("indexing_jobs", sa.Column("note_id", UUID))
    op.add_column("indexing_jobs", sa.Column("note_version_id", UUID))
    op.add_column("indexing_jobs", sa.Column("operation", sa.Text(), server_default="upsert_version", nullable=False))
    op.add_column("indexing_jobs", sa.Column("priority", sa.Integer(), server_default="0", nullable=False))
    op.add_column("indexing_jobs", sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False))
    op.add_column("indexing_jobs", sa.Column("claimed_by", sa.Text()))
    op.add_column("indexing_jobs", sa.Column("lease_expires_at", sa.DateTime(timezone=True)))
    op.add_column("indexing_jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
    op.add_column("indexing_jobs", sa.Column("error_code", sa.Text()))
    op.alter_column("indexing_jobs", "started_at", existing_type=sa.DateTime(timezone=True), nullable=True, server_default=None)

    # Note jobs were historically represented in JSON metadata. Preserve them,
    # and classify targetless legacy administrative rows as rebuild requests.
    op.execute(
        """
        UPDATE indexing_jobs
        SET note_id = CASE
              WHEN (metadata->>'note_id') ~* '^[0-9a-f-]{36}$'
              THEN (metadata->>'note_id')::uuid ELSE NULL END,
            asset_type = CASE WHEN metadata->>'entity_type' = 'note' THEN 'note' ELSE 'document' END
        """
    )
    op.execute(
        """
        UPDATE indexing_jobs j
        SET note_version_id = v.id
        FROM note_versions v
        WHERE j.note_id = v.note_id
          AND COALESCE(j.metadata->>'note_revision', '') ~ '^[0-9]+$'
          AND v.revision = (j.metadata->>'note_revision')::integer
        """
    )
    op.execute(
        """
        UPDATE indexing_jobs j
        SET note_id = NULL, note_version_id = NULL, asset_type = 'document'
        WHERE note_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM notes n WHERE n.id = j.note_id)
        """
    )
    op.execute(
        """
        UPDATE indexing_jobs
        SET operation = CASE
            WHEN document_id IS NULL AND note_id IS NULL THEN 'rebuild_scope'
            WHEN COALESCE(metadata->>'action','') IN ('deleted','delete') THEN 'delete_asset'
            WHEN COALESCE(metadata->>'action','') IN ('moved','renamed','metadata') THEN 'refresh_metadata'
            ELSE 'upsert_version' END
        """
    )
    op.execute(
        """
        UPDATE indexing_jobs SET status = CASE status
          WHEN 'running' THEN 'claimed'
          WHEN 'succeeded' THEN 'completed'
          WHEN 'skipped' THEN 'superseded'
          ELSE status END
        """
    )
    op.execute(
        """
        WITH ranked AS (
          SELECT id,
                 row_number() OVER (
                   PARTITION BY note_version_id, operation
                   ORDER BY created_at, id
                 ) AS ordinal
          FROM indexing_jobs
          WHERE note_version_id IS NOT NULL
            AND status IN (
              'pending','claimed','extracting','chunked',
              'embedding','writing','verifying','retry_wait'
            )
        )
        UPDATE indexing_jobs j
        SET status = 'superseded',
            completed_at = now(),
            message = 'Superseded while deduplicating legacy note jobs.'
        FROM ranked r
        WHERE j.id = r.id AND r.ordinal > 1
        """
    )

    op.create_foreign_key("fk_indexing_jobs_note_id", "indexing_jobs", "notes", ["note_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key(
        "fk_indexing_jobs_note_version_id",
        "indexing_jobs",
        "note_versions",
        ["note_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_indexing_jobs_status",
        "indexing_jobs",
        "status in ('pending','claimed','extracting','chunked','embedding','writing',"
        "'verifying','completed','retry_wait','failed','superseded','cancelled')",
    )
    op.create_check_constraint(
        "ck_indexing_jobs_operation",
        "indexing_jobs",
        "operation in ('upsert_version','delete_asset','refresh_metadata','reprocess_version','rebuild_scope')",
    )
    op.create_check_constraint(
        "ck_indexing_jobs_target_family",
        "indexing_jobs",
        "(operation = 'rebuild_scope') OR "
        "(asset_type = 'document' AND document_id IS NOT NULL AND note_id IS NULL AND note_version_id IS NULL) OR "
        "(asset_type = 'note' AND note_id IS NOT NULL AND document_id IS NULL AND document_version_id IS NULL)",
    )
    op.create_index("ix_indexing_jobs_claim_order", "indexing_jobs", ["status", "available_at", "priority", "created_at"])
    op.create_index("ix_indexing_jobs_lease_recovery", "indexing_jobs", ["lease_expires_at", "status"])
    op.create_index("ix_indexing_jobs_note_id", "indexing_jobs", ["note_id"])
    op.create_index("ix_indexing_jobs_note_version_id", "indexing_jobs", ["note_version_id"])
    op.execute(
        f"CREATE UNIQUE INDEX uq_indexing_jobs_active_document_operation "
        f"ON indexing_jobs (document_version_id, operation) "
        f"WHERE document_version_id IS NOT NULL AND status IN ({ACTIVE})"
    )
    op.execute(
        f"CREATE UNIQUE INDEX uq_indexing_jobs_active_note_operation "
        f"ON indexing_jobs (note_version_id, operation) "
        f"WHERE note_version_id IS NOT NULL AND status IN ({ACTIVE})"
    )

    op.create_table(
        "indexer_workers",
        sa.Column("worker_id", sa.Text(), primary_key=True),
        sa.Column("service_state", sa.Text(), server_default="starting", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        sa.Column("current_job_id", UUID, sa.ForeignKey("indexing_jobs.id", ondelete="SET NULL")),
        sa.Column("reconciliation_state", sa.Text()),
        sa.Column("last_reconciliation_at", sa.DateTime(timezone=True)),
        sa.Column("embedding_device", sa.Text()),
        sa.Column("embedding_precision", sa.Text()),
        sa.Column("metrics", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("last_error_code", sa.Text()),
    )
    op.create_table(
        "index_generations",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column("generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bm25_generation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("bm25_snapshot_path", sa.Text()),
        sa.Column("qdrant_collection", sa.Text()),
        sa.Column("point_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("published_by", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("index_generations")
    op.drop_table("indexer_workers")
    op.execute("DROP INDEX IF EXISTS uq_indexing_jobs_active_note_operation")
    op.execute("DROP INDEX IF EXISTS uq_indexing_jobs_active_document_operation")
    for index in (
        "ix_indexing_jobs_note_version_id",
        "ix_indexing_jobs_note_id",
        "ix_indexing_jobs_lease_recovery",
        "ix_indexing_jobs_claim_order",
    ):
        op.drop_index(index, table_name="indexing_jobs")
    op.drop_constraint("ck_indexing_jobs_target_family", "indexing_jobs", type_="check")
    op.drop_constraint("ck_indexing_jobs_operation", "indexing_jobs", type_="check")
    op.drop_constraint("ck_indexing_jobs_status", "indexing_jobs", type_="check")
    op.execute(
        """
        UPDATE indexing_jobs SET status = CASE status
          WHEN 'claimed' THEN 'running'
          WHEN 'extracting' THEN 'running'
          WHEN 'chunked' THEN 'running'
          WHEN 'embedding' THEN 'running'
          WHEN 'writing' THEN 'running'
          WHEN 'verifying' THEN 'running'
          WHEN 'completed' THEN 'succeeded'
          WHEN 'retry_wait' THEN 'pending'
          WHEN 'superseded' THEN 'skipped'
          WHEN 'cancelled' THEN 'skipped'
          ELSE status END
        """
    )
    op.create_check_constraint(
        "ck_indexing_jobs_status",
        "indexing_jobs",
        "status in ('pending','running','succeeded','failed','skipped')",
    )
    op.drop_constraint("fk_indexing_jobs_note_version_id", "indexing_jobs", type_="foreignkey")
    op.drop_constraint("fk_indexing_jobs_note_id", "indexing_jobs", type_="foreignkey")
    for column in (
        "error_code",
        "heartbeat_at",
        "lease_expires_at",
        "claimed_by",
        "max_attempts",
        "priority",
        "operation",
        "note_version_id",
        "note_id",
        "asset_type",
    ):
        op.drop_column("indexing_jobs", column)
    op.create_index(
        "uq_indexing_jobs_active_document_version",
        "indexing_jobs",
        ["document_version_id"],
        unique=True,
        postgresql_where=sa.text("document_version_id IS NOT NULL AND status IN ('pending','running')"),
    )
