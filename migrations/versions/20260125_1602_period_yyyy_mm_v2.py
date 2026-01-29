
# migrations/versions/20260125_1602_period_yyyy_mm_v2.py
# Title: Harmonize all period columns to YYYY-MM across the schema (v2)
from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers (must be top-level) ----
revision = "20260125_1602_period_yyyy_mm_v2"
down_revision = "20260122_2310_crs_alignment_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Helpers kept inside upgrade to avoid module import issues
    def has_table(t: str) -> bool:
        return bool(
            conn.execute(
                sa.text(
                    "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=:t"
                ),
                {"t": t},
            ).fetchone()
        )

    def has_check(t: str, chk: str) -> bool:
        return bool(
            conn.execute(
                sa.text(
                    "SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
                    "WHERE CONSTRAINT_SCHEMA = DATABASE() "
                    "AND TABLE_NAME=:t AND CONSTRAINT_TYPE='CHECK' AND CONSTRAINT_NAME=:c"
                ),
                {"t": t, "c": chk},
            ).fetchone()
        )

    def col_type(t: str, c: str) -> str:
        return (
            conn.execute(
                sa.text(
                    "SELECT CONCAT(DATA_TYPE,'(',IFNULL(CHARACTER_MAXIMUM_LENGTH,''),')') "
                    "FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=:t AND COLUMN_NAME=:c"
                ),
                {"t": t, "c": c},
            ).scalar()
            or ""
        ).lower()

    def has_index(t: str, idx: str) -> bool:
        return bool(
            conn.execute(
                sa.text(
                    "SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=:t AND INDEX_NAME=:i"
                ),
                {"t": t, "i": idx},
            ).fetchone()
        )

    def normalize_to_yyyy_mm(table: str, col: str, force_varchar7: bool = True) -> None:
        if not has_table(table):
            return
        # 1) Normalize data values to YYYY-MM
        conn.execute(
            sa.text(
                f"""
                UPDATE `{table}`
                SET `{col}` =
                CASE
                  WHEN `{col}` IS NULL OR `{col}`='' THEN `{col}`
                  WHEN `{col}` REGEXP '^[0-9]{{4}}-(0[1-9]|1[0-2])$' THEN `{col}`
                  WHEN `{col}` LIKE 'COM_%' THEN SUBSTRING(`{col}`,5,7)
                  WHEN `{col}` REGEXP '^[0-9]{{4}}/(0[1-9]|1[0-2])$' THEN REPLACE(`{col}`,'/','-')
                  WHEN `{col}` REGEXP '^[A-Za-z]{{3}} [0-9]{{4}}$'
                       THEN DATE_FORMAT(STR_TO_DATE(CONCAT('01 ', `{col}`),'%d %b %Y'),'%Y-%m')
                  WHEN `{col}` REGEXP '^[A-Za-z]{{4,}} [0-9]{{4}}$'
                       THEN DATE_FORMAT(STR_TO_DATE(CONCAT('01 ', `{col}`),'%d %M %Y'),'%Y-%m')
                  WHEN `{col}` REGEXP '^[0-9]{{4}}-(0?[1-9]|1[0-2])$'
                       THEN CONCAT(LEFT(`{col}`,4),'-',LPAD(SUBSTRING_INDEX(`{col}`,'-',-1),2,'0'))
                  WHEN `{col}` REGEXP '^[0-9]{{4}}(0[1-9]|1[0-2])$'
                       THEN CONCAT(LEFT(`{col}`,4),'-',RIGHT(`{col}`,2))
                  ELSE `{col}`
                END
                WHERE `{col}` IS NOT NULL AND `{col}` <> '';
                """
            )
        )
        # 2) Ensure type is VARCHAR(7) (skip when instructed)
        if force_varchar7 and col_type(table, col) != "varchar(7)":
            conn.execute(
                sa.text(f"ALTER TABLE `{table}` MODIFY COLUMN `{col}` VARCHAR(7) NULL;")
            )
        # 3) Add CHECK if missing
        chk_name = f"chk_{table}_{col}_yyyy_mm"
        if not has_check(table, chk_name):
            conn.execute(
                sa.text(
                    f"ALTER TABLE `{table}` "
                    f"ADD CONSTRAINT `{chk_name}` "
                    f"CHECK (`{col}` IS NULL OR `{col}` REGEXP '^[0-9]{{4}}-(0[1-9]|1[0-2])$');"
                )
            )

    # Disable FKs for mass updates/alters (split into separate statements)
    conn.execute(sa.text("SET @old_fk = @@FOREIGN_KEY_CHECKS"))
    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS = 0"))

    # Targets derived from your migrations & dump (month fields across tables)
    # statement/schedule/terminated/uploads (core) – plus reporting & audit tables.
    targets = [
        ("statement", "MONTH_YEAR", True),
        ("schedule", "month_year", True),
        ("terminated", "month_year", True),
        ("uploads", "month_year", True),
        ("monthly_reports", "report_period", True),
        ("cli_runs", "report_period", True),
        ("active_policies", "last_seen_month_year", True),
        ("audit_flags", "month_year", True),
        ("discrepancies", "period", True),
        ("discrepancies", "month_year", True),
        # expected_commissions.period is already intended as YYYY-MM; keep type but still normalize
        ("expected_commissions", "period", False),
    ]
    for t, c, force7 in targets:
        normalize_to_yyyy_mm(t, c, force_varchar7=force7)

    # Recreate helpful indexes (only if absent) aligned to your schema
    # statement(agent_code, MONTH_YEAR, policy_no)
    if has_table("statement") and not has_index("statement", "ix_statement_agent_month_pol"):
        conn.execute(
            sa.text(
                "CREATE INDEX `ix_statement_agent_month_pol` "
                "ON `statement`(`agent_code`,`MONTH_YEAR`,`policy_no`);"
            )
        )
    # terminated(agent_code, month_year, policy_no)
    if has_table("terminated") and not has_index("terminated", "ix_terminated_agent_month_pol"):
        conn.execute(
            sa.text(
                "CREATE INDEX `ix_terminated_agent_month_pol` "
                "ON `terminated`(`agent_code`,`month_year`,`policy_no`);"
            )
        )
    # expected_commissions(upload_id)
    if has_table("expected_commissions") and not has_index("expected_commissions", "ix_expected_upload"):
        conn.execute(
            sa.text(
                "CREATE INDEX `ix_expected_upload` ON `expected_commissions`(`upload_id`);"
            )
        )

    # Restore FKs
    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS = @old_fk;"))


def downgrade() -> None:
    conn = op.get_bind()

    # Disable FKs (split into separate statements)
    conn.execute(sa.text("SET @old_fk = @@FOREIGN_KEY_CHECKS"))
    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS = 0"))

    # Only drop the CHECK constraints (keeps the columns as VARCHAR(7))
    checks = [
        ("statement", "MONTH_YEAR"),
        ("schedule", "month_year"),
        ("terminated", "month_year"),
        ("uploads", "month_year"),
        ("monthly_reports", "report_period"),
        ("cli_runs", "report_period"),
        ("active_policies", "last_seen_month_year"),
        ("audit_flags", "month_year"),
        ("discrepancies", "period"),
        ("discrepancies", "month_year"),
        ("expected_commissions", "period"),
    ]
    for t, c in checks:
        # ensure table exists
        if not (
            conn.execute(
                sa.text(
                    "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=:t"
                ),
                {"t": t},
            ).fetchone()
        ):
            continue
        chk = f"chk_{t}_{c}_yyyy_mm"
        exists = conn.execute(
            sa.text(
                "SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS "
                "WHERE CONSTRAINT_SCHEMA = DATABASE() "
                "AND TABLE_NAME=:t AND CONSTRAINT_TYPE='CHECK' AND CONSTRAINT_NAME=:c"
            ),
            {"t": t, "c": chk},
        ).fetchone()
        if exists:
            conn.execute(sa.text(f"ALTER TABLE `{t}` DROP CHECK `{chk}`;"))

    # Restore FKs
    conn.execute(sa.text("SET FOREIGN_KEY_CHECKS = @old_fk;"))