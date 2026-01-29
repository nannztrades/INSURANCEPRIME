
# migrations/versions/20260122_2310_crs_alignment_v2.py
# CRS alignment v2 (2026-01-22)
# - Add statement.receipt_no (VARCHAR(64) NULL)
# - Ensure statement.pay_date is DATE NULL (drop/re-add if needed; no backfill)
# - FKs: statement/schedule/terminated.upload_id -> uploads.UploadID (CASCADE/CASCADE)
#        users.agent_code -> agents.agent_code (SET NULL/CASCADE)
# - UNIQUE(agent_code, month_year, doc_type, is_active) on uploads
# - Indexes: statement(agent_code, MONTH_YEAR, policy_no)
#            terminated(agent_code, month_year, policy_no)
#            expected_commissions(upload_id)

from alembic import op
import sqlalchemy as sa
from typing import Optional

revision = "20260122_2310_crs_alignment_v2"
down_revision = "20260121_2239_icrs_schema_alignment"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SHOW COLUMNS FROM `{t}` LIKE :c".format(t=table)),
        {"c": column},
    ).fetchall()
    return bool(rows)


def _col_type(table: str, column: str) -> Optional[str]:
    conn = op.get_bind()
    return conn.execute(
        sa.text(
            """
            SELECT DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :t
              AND COLUMN_NAME = :c
            """
        ),
        {"t": table, "c": column},
    ).scalar()


def _has_index(table: str, index_name: str) -> bool:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SHOW INDEX FROM `{t}` WHERE Key_name = :k".format(t=table)),
        {"k": index_name},
    ).fetchall()
    return bool(rows)


def _has_fk(table: str, fk_name: str) -> bool:
    conn = op.get_bind()
    db = conn.execute(sa.text("SELECT DATABASE()")).scalar()
    rows = conn.execute(
        sa.text(
            """
            SELECT CONSTRAINT_NAME
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = :db
              AND TABLE_NAME = :t
              AND CONSTRAINT_NAME = :fk
            """
        ),
        {"db": db, "t": table, "fk": fk_name},
    ).fetchall()
    return bool(rows)


def upgrade() -> None:
    # 1) Add receipt_no
    if not _has_column("statement", "receipt_no"):
        op.execute(
            "ALTER TABLE `statement` "
            "ADD COLUMN `receipt_no` VARCHAR(64) NULL AFTER `policy_no`;"
        )

    # 2) Ensure pay_date is DATE NULL
    if _has_column("statement", "pay_date"):
        dtype = (_col_type("statement", "pay_date") or "").lower()
        if dtype != "date":
            op.execute("ALTER TABLE `statement` DROP COLUMN `pay_date`;")
            op.execute(
                "ALTER TABLE `statement` "
                "ADD COLUMN `pay_date` DATE NULL AFTER `policy_type`;"
            )

    # 3) Foreign keys
    fks = [
        ("statement",  "fk_statement_upload",       "upload_id",  "uploads", "UploadID",  "CASCADE",  "CASCADE"),
        ("schedule",   "fk_schedule_upload",        "upload_id",  "uploads", "UploadID",  "CASCADE",  "CASCADE"),
        ("terminated", "fk_terminated_upload",      "upload_id",  "uploads", "UploadID",  "CASCADE",  "CASCADE"),
        ("users",      "fk_users_agent_code_agents","agent_code", "agents",  "agent_code","SET NULL", "CASCADE"),
    ]
    for table, fk_name, col, parent, pcol, on_del, on_upd in fks:
        if not _has_fk(table, fk_name):
            idx_name = f"ix_{table}_{col}"
            if not _has_index(table, idx_name):
                op.execute(f"CREATE INDEX `{idx_name}` ON `{table}`(`{col}`);")
            op.execute(
                (
                    "ALTER TABLE `{t}` "
                    "ADD CONSTRAINT `{fk}` FOREIGN KEY (`{c}`) "
                    "REFERENCES `{p}`(`{pc}`) ON DELETE {od} ON UPDATE {ou};"
                ).format(t=table, fk=fk_name, c=col, p=parent, pc=pcol, od=on_del, ou=on_upd)
            )

    # 4) UNIQUE single active tuple
    if not _has_index("uploads", "ux_uploads_active_tuple"):
        op.execute(
            """
            ALTER TABLE `uploads`
            ADD UNIQUE KEY `ux_uploads_active_tuple`
            (`agent_code`, `month_year`, `doc_type`, `is_active`);
            """
        )

    # 5) Supporting indexes
    if not _has_index("statement", "ix_statement_agent_month_pol"):
        op.execute(
            "CREATE INDEX `ix_statement_agent_month_pol` "
            "ON `statement`(`agent_code`,`MONTH_YEAR`,`policy_no`);"
        )
    if not _has_index("terminated", "ix_terminated_agent_month_pol"):
        op.execute(
            "CREATE INDEX `ix_terminated_agent_month_pol` "
            "ON `terminated`(`agent_code`,`month_year`,`policy_no`);"
        )
    if not _has_index("expected_commissions", "ix_expected_upload"):
        op.execute(
            "CREATE INDEX `ix_expected_upload` "
            "ON `expected_commissions`(`upload_id`);"
        )


def downgrade() -> None:
    # Drop indexes (reverse order)
    if _has_index("expected_commissions", "ix_expected_upload"):
        op.execute("DROP INDEX `ix_expected_upload` ON `expected_commissions`;")
    if _has_index("terminated", "ix_terminated_agent_month_pol"):
        op.execute("DROP INDEX `ix_terminated_agent_month_pol` ON `terminated`;")
    if _has_index("statement", "ix_statement_agent_month_pol"):
        op.execute("DROP INDEX `ix_statement_agent_month_pol` ON `statement`;")
    if _has_index("uploads", "ux_uploads_active_tuple"):
        op.execute("DROP INDEX `ux_uploads_active_tuple` ON `uploads`;")

    # Drop FKs
    for table, fk_name in [
        ("users", "fk_users_agent_code_agents"),
        ("terminated", "fk_terminated_upload"),
        ("schedule", "fk_schedule_upload"),
        ("statement", "fk_statement_upload"),
    ]:
        if _has_fk(table, fk_name):
            op.execute(f"ALTER TABLE `{table}` DROP FOREIGN KEY `{fk_name}`;")

    # Revert pay_date to VARCHAR
    if _has_column("statement", "pay_date"):
        op.execute("ALTER TABLE `statement` MODIFY COLUMN `pay_date` VARCHAR(32) NULL;")

    # Drop receipt_no
    if _has_column("statement", "receipt_no"):
        op.execute("ALTER TABLE `statement` DROP COLUMN `receipt_no`;")
