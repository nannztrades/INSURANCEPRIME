
# migrations/versions/20260125_1601_period_yyyy_mm.py
# Title: Harmonize all period columns to YYYY-MM across the schema
from alembic import op
import sqlalchemy as sa

revision = "20260125_1601_period_yyyy_mm"
down_revision = "20260122_2310_crs_alignment_v2"
branch_labels = None
depends_on = None

# ---------- helpers ----------
def _exec(sql: str) -> None:
    """
    Execute 1..N SQL statements safely (split on ';') so that each
    call to the DB driver runs a single statement.
    """
    parts = [s.strip() for s in (sql or "").split(";")]
    for stmt in parts:
        if stmt:
            op.execute(sa.text(stmt))

def _has_check(table: str, name: str) -> bool:
    sql = sa.text("""
        SELECT 1
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE()
          AND TABLE_NAME = :t
          AND CONSTRAINT_TYPE = 'CHECK'
          AND CONSTRAINT_NAME = :n
    """)
    return bool(op.get_bind().execute(sql, {"t": table, "n": name}).fetchone())

def _col_type(table: str, col: str) -> str:
    sql = sa.text("""
        SELECT CONCAT(DATA_TYPE,'(',IFNULL(CHARACTER_MAXIMUM_LENGTH,''),')')
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :t AND COLUMN_NAME = :c
    """)
    v = op.get_bind().execute(sql, {"t": table, "c": col}).scalar()
    return (v or "").lower()

def _has_table(table: str) -> bool:
    sql = sa.text("""
        SELECT 1 FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t
    """)
    return bool(op.get_bind().execute(sql, {"t": table}).fetchone())

def _has_index(table: str, index: str) -> bool:
    sql = sa.text("""
        SELECT 1
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :t
          AND INDEX_NAME = :i
    """)
    return bool(op.get_bind().execute(sql, {"t": table, "i": index}).fetchone())

# normalize any variant (e.g., "Jun 2025", "COM_2025-06", "2025/06") to "YYYY-MM"
def _normalize_sql(backticked_col: str) -> str:
    c = backticked_col  # e.g., `month_year`
    return f"""
    CASE
      WHEN {c} IS NULL OR {c}='' THEN {c}
      WHEN {c} REGEXP '^[0-9]{{4}}-(0[1-9]|1[0-2])$' THEN {c}
      WHEN {c} LIKE 'COM_%' THEN SUBSTRING({c}, 5, 7)
      WHEN {c} REGEXP '^[0-9]{{4}}/(0[1-9]|1[0-2])$' THEN REPLACE({c}, '/', '-')
      WHEN {c} REGEXP '^[A-Za-z]{{3}} [0-9]{{4}}$'
        THEN DATE_FORMAT(STR_TO_DATE(CONCAT('01 ', {c}), '%d %b %Y'), '%Y-%m')
      WHEN {c} REGEXP '^[A-Za-z]{{4,}} [0-9]{{4}}$'
        THEN DATE_FORMAT(STR_TO_DATE(CONCAT('01 ', {c}), '%d %M %Y'), '%Y-%m')
      WHEN {c} REGEXP '^[0-9]{{4}}-(0?[1-9]|1[0-2])$'
        THEN CONCAT(LPAD(SUBSTRING_INDEX({c},'-',1),4,'0'), '-', LPAD(SUBSTRING_INDEX({c},'-',-1),2,'0'))
      WHEN {c} REGEXP '^[0-9]{{4}}(0[1-9]|1[0-2])$'
        THEN CONCAT(SUBSTRING({c},1,4),'-',SUBSTRING({c},5,2))
      ELSE {c}
    END
    """

def _alter_to_varchar7(table: str, col: str):
    if _col_type(table, col) != "varchar(7)":
        _exec(f"ALTER TABLE `{table}` MODIFY COLUMN `{col}` VARCHAR(7) NULL;")

def _add_check_yyyy_mm(table: str, col: str):
    chk = f"chk_{table}_{col}_yyyy_mm"
    if not _has_check(table, chk):
        _exec(f"""
            ALTER TABLE `{table}`
            ADD CONSTRAINT `{chk}`
            CHECK (`{col}` IS NULL OR `{col}` REGEXP '^[0-9]{{4}}-(0[1-9]|1[0-2])$')
        """)

# ---------- migration ----------
def upgrade() -> None:
    # turn off FKs to be safe during mass updates/alter (split per statement by _exec)
    _exec("SET @old_fk = @@FOREIGN_KEY_CHECKS; SET FOREIGN_KEY_CHECKS = 0;")

    targets = [
        ("statement", "MONTH_YEAR"),
        ("schedule", "month_year"),
        ("terminated", "month_year"),
        ("uploads", "month_year"),
        ("monthly_reports", "report_period"),
        ("cli_runs", "report_period"),
        ("active_policies", "last_seen_month_year"),
        ("audit_flags", "month_year"),     # ← fixed: correct column name
        ("discrepancies", "period"),
        ("discrepancies", "month_year"),
        # expected_commissions.period already intended as YYYY-MM; still normalize but don't force type
        ("expected_commissions", "period"),
    ]

    for table, col in targets:
        if not _has_table(table):
            continue

        # normalize values to YYYY-MM
        _exec(f"""
            UPDATE `{table}`
            SET `{col}` = {_normalize_sql('`' + col + '`')}
            WHERE `{col}` IS NOT NULL AND `{col}` <> '';
        """)

        # set VARCHAR(7) except for expected_commissions.period
        if not (table == "expected_commissions" and col == "period"):
            _alter_to_varchar7(table, col)

        # add CHECK to enforce format
        _add_check_yyyy_mm(table, col)

    # (re)create helpful composite indexes only if missing
    if _has_table("statement") and not _has_index("statement", "ix_statement_agent_month_pol"):
        _exec("""
            CREATE INDEX `ix_statement_agent_month_pol`
            ON `statement`(`agent_code`,`MONTH_YEAR`,`policy_no`);
        """)
    if _has_table("terminated") and not _has_index("terminated", "ix_terminated_agent_month_pol"):
        _exec("""
            CREATE INDEX `ix_terminated_agent_month_pol`
            ON `terminated`(`agent_code`,`month_year`,`policy_no`);
        """)
    if _has_table("expected_commissions") and not _has_index("expected_commissions", "ix_expected_upload"):
        _exec("""
            CREATE INDEX `ix_expected_upload`
            ON `expected_commissions`(`upload_id`);
        """)

    _exec("SET FOREIGN_KEY_CHECKS = @old_fk;")

def downgrade() -> None:
    # drop only the CHECK constraints (leave VARCHAR(7) as-is)
    _exec("SET @old_fk = @@FOREIGN_KEY_CHECKS; SET FOREIGN_KEY_CHECKS = 0;")

    for table, col in [
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
    ]:
        if not _has_table(table):
            continue
        chk = f"chk_{table}_{col}_yyyy_mm"
        if _has_check(table, chk):
            _exec(f"ALTER TABLE `{table}` DROP CHECK `{chk}`;")

    _exec("SET FOREIGN_KEY_CHECKS = @old_fk;")
