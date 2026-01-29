
# migrations/versions/20260127_0300_tokens_fk_and_invoker_views.py
from alembic import op
import sqlalchemy as sa

# Revision identifiers.
revision = "20260127_0300_tokens_fk_and_invoker_views"
down_revision = "3f2e33b3c740"
branch_labels = None
depends_on = None

def _exec(sql: str) -> None:
    for stmt in [s.strip() for s in (sql or "").split(";")]:
        if stmt:
            op.execute(sa.text(stmt))

def _scalar(sql: str, **p):
    return op.get_bind().execute(sa.text(sql), p).scalar()

def _has_fk(table: str, fk_name: str) -> bool:
    db = _scalar("SELECT DATABASE()")
    sql = """
    SELECT 1
    FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA=:db AND TABLE_NAME=:t AND CONSTRAINT_NAME=:fk
    """
    return bool(_scalar(sql, db=db, t=table, fk=fk_name))

def _column_type(table: str, col: str) -> str:
    sql = """
    SELECT COLUMN_TYPE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = :t
      AND COLUMN_NAME = :c
    """
    return (_scalar(sql, t=table, c=col) or "").strip()

def _has_view(view: str) -> bool:
    sql = """
    SELECT 1 FROM INFORMATION_SCHEMA.VIEWS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=:v
    """
    return bool(_scalar(sql, v=view))

def _has_any_index_on_column(table: str, col: str) -> bool:
    sql = """
    SELECT 1
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = :t
      AND COLUMN_NAME = :c
    LIMIT 1
    """
    return bool(_scalar(sql, t=table, c=col))

def upgrade() -> None:
    # --- 1) auth_refresh_tokens.user_id => ensure type matches users.id, cleanup, add FK ---

    # Delete tokens referencing non-existent users (orphan cleanup)
    _exec("""
        DELETE rt FROM `auth_refresh_tokens` rt
        LEFT JOIN `users` u ON u.`id` = rt.`user_id`
        WHERE u.`id` IS NULL
    """)

    # Match user_id column type to users.id exactly (e.g., INT vs BIGINT)  [1](https://dpworld-my.sharepoint.com/personal/nana_obeng_dpwssa_com/Documents/Microsoft%20Copilot%20Chat%20Files/insurancelocal.sql)
    users_id_type = _column_type("users", "id") or "INT"
    # Normalize whitespace/case
    users_id_type_norm = users_id_type.upper().replace(" UNSIGNED", "").replace("SIGNED", "").strip()
    # Current type of auth_refresh_tokens.user_id
    art_user_type = _column_type("auth_refresh_tokens", "user_id").upper().strip()

    if art_user_type != users_id_type_norm:
        _exec(f"ALTER TABLE `auth_refresh_tokens` MODIFY COLUMN `user_id` {users_id_type_norm} NOT NULL")

    # Ensure there is an index on user_id (some dumps already have `ix_tokens_user`)  [1](https://dpworld-my.sharepoint.com/personal/nana_obeng_dpwssa_com/Documents/Microsoft%20Copilot%20Chat%20Files/insurancelocal.sql)
    if not _has_any_index_on_column("auth_refresh_tokens", "user_id"):
        # Create a deterministic index name if truly missing (no IF NOT EXISTS)
        _exec("CREATE INDEX `ix_refresh_user` ON `auth_refresh_tokens`(`user_id`)")

    # Add FK only if missing
    if not _has_fk("auth_refresh_tokens", "fk_refresh_user"):
        _exec("""
            ALTER TABLE `auth_refresh_tokens`
            ADD CONSTRAINT `fk_refresh_user`
            FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
            ON DELETE CASCADE ON UPDATE CASCADE
        """)

    # --- 2) Recreate views with SQL SECURITY INVOKER (avoid DEFINER issues in non-local envs)  [1](https://dpworld-my.sharepoint.com/personal/nana_obeng_dpwssa_com/Documents/Microsoft%20Copilot%20Chat%20Files/insurancelocal.sql) ---

    for v in ("agents_v", "schedule_v", "statement_v", "terminated_v"):
        if _has_view(v):
            _exec(f"DROP VIEW `{v}`")

    # agents_v
    _exec("""
        CREATE SQL SECURITY INVOKER VIEW `agents_v` AS
        SELECT a.`agent_code` AS `agent_code`,
               a.`agent_name` AS `agent_name`,
               a.`license_number` AS `license_number`,
               a.`is_active` AS `is_active`,
               (CASE WHEN (a.`is_active` = 1) THEN 'ACTIVE' ELSE 'INACTIVE' END) AS `status`,
               a.`created_at` AS `created_at`,
               a.`updated_at` AS `updated_at`,
               a.`agent_provided_earliest_date` AS `agent_provided_earliest_date`
        FROM `agents` a
    """)

    # schedule_v
    _exec("""
        CREATE SQL SECURITY INVOKER VIEW `schedule_v` AS
        SELECT `schedule`.`schedule_id` AS `schedule_id`,
               `schedule`.`upload_id` AS `upload_id`,
               `schedule`.`agent_code` AS `agent_code`,
               `schedule`.`agent_name` AS `agent_name`,
               `schedule`.`AGENT_LICENSE_NUMBER` AS `AGENT_LICENSE_NUMBER`,
               `schedule`.`commission_batch_code` AS `commission_batch_code`,
               `schedule`.`total_premiums` AS `total_premiums`,
               `schedule`.`income` AS `income`,
               `schedule`.`gov_tax` AS `gov_tax`,
               `schedule`.`siclase` AS `siclase`,
               `schedule`.`welfareko` AS `welfareko`,
               `schedule`.`premium_deduction` AS `premium_deduction`,
               `schedule`.`pensions` AS `pensions`,
               `schedule`.`total_deductions` AS `total_deductions`,
               `schedule`.`net_commission` AS `net_commission`,
               `schedule`.`document_date` AS `document_date`,
               `schedule`.`month_year` AS `month_year`
        FROM `schedule`
    """)

    # statement_v
    _exec("""
        CREATE SQL SECURITY INVOKER VIEW `statement_v` AS
        SELECT `statement`.`statement_id` AS `statement_id`,
               `statement`.`upload_id` AS `upload_id`,
               `statement`.`agent_code` AS `agent_code`,
               `statement`.`policy_no` AS `policy_no`,
               `statement`.`holder` AS `holder`,
               `statement`.`surname` AS `surname`,
               `statement`.`other_name` AS `other_name`,
               `statement`.`policy_type` AS `policy_type`,
               `statement`.`term` AS `term`,
               `statement`.`pay_date` AS `pay_date`,
               `statement`.`receipt_no` AS `receipt_no`,
               `statement`.`premium` AS `premium`,
               `statement`.`com_rate` AS `com_rate`,
               `statement`.`com_amt` AS `com_amt`,
               `statement`.`inception` AS `inception`,
               `statement`.`agent_name` AS `agent_name`,
               `statement`.`MONTH_YEAR` AS `month_year`,
               `statement`.`AGENT_LICENSE_NUMBER` AS `AGENT_LICENSE_NUMBER`,
               `statement`.`unique_id_hash` AS `unique_id_hash`,
               `statement`.`period_date` AS `period_date`
        FROM `statement`
    """)

    # terminated_v
    _exec("""
        CREATE SQL SECURITY INVOKER VIEW `terminated_v` AS
        SELECT `terminated`.`terminated_id` AS `terminated_id`,
               `terminated`.`upload_id` AS `upload_id`,
               `terminated`.`agent_code` AS `agent_code`,
               `terminated`.`policy_no` AS `policy_no`,
               `terminated`.`holder` AS `holder`,
               `terminated`.`surname` AS `surname`,
               `terminated`.`other_name` AS `other_name`,
               `terminated`.`receipt_no` AS `receipt_no`,
               `terminated`.`paydate` AS `paydate`,
               `terminated`.`premium` AS `premium`,
               `terminated`.`com_rate` AS `com_rate`,
               `terminated`.`com_amt` AS `com_amt`,
               `terminated`.`policy_type` AS `policy_type`,
               `terminated`.`inception` AS `inception`,
               `terminated`.`status` AS `status`,
               `terminated`.`agent_name` AS `agent_name`,
               `terminated`.`reason` AS `reason`,
               `terminated`.`month_year` AS `month_year`,
               `terminated`.`AGENT_LICENSE_NUMBER` AS `AGENT_LICENSE_NUMBER`,
               `terminated`.`termination_date` AS `termination_date`
        FROM `terminated`
    """)

def downgrade() -> None:
    # Drop FK if present
    if _has_fk("auth_refresh_tokens", "fk_refresh_user"):
        _exec("ALTER TABLE `auth_refresh_tokens` DROP FOREIGN KEY `fk_refresh_user`")
    # Drop INVOKER views
    for v in ("agents_v", "schedule_v", "statement_v", "terminated_v"):
        if _has_view(v):
            _exec(f"DROP VIEW `{v}`")
