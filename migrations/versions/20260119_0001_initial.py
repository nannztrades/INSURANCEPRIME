
# migrations/versions/20260119_0001_initial.py
# Initial schema for ICRS MySQL tables
from alembic import op
import sqlalchemy as sa

# Revision identifiers, used by Alembic.
revision = "20260119_0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Users
    op.execute("""
    CREATE TABLE IF NOT EXISTS `users` (
      `id` INT NOT NULL AUTO_INCREMENT,
      `email` VARCHAR(191) NOT NULL,
      `role` VARCHAR(32) NOT NULL,
      `agent_code` VARCHAR(64) NULL,
      `is_active` TINYINT(1) NOT NULL DEFAULT 1,
      `last_login` DATETIME NULL,
      `password_hash` VARCHAR(255) NOT NULL,
      PRIMARY KEY (`id`),
      UNIQUE KEY `ux_users_email` (`email`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Agents
    op.execute("""
    CREATE TABLE IF NOT EXISTS `agents` (
      `agent_code` VARCHAR(64) NOT NULL,
      `agent_name` VARCHAR(191) NULL,
      `license_number` VARCHAR(64) NULL,
      `agent_provided_earliest_date` VARCHAR(32) NULL,
      `is_active` TINYINT(1) NOT NULL DEFAULT 1,
      `created_at` DATETIME NOT NULL,
      `updated_at` DATETIME NOT NULL,
      PRIMARY KEY (`agent_code`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Uploads
    op.execute("""
    CREATE TABLE IF NOT EXISTS `uploads` (
      `UploadID` INT NOT NULL AUTO_INCREMENT,
      `agent_code` VARCHAR(64) NOT NULL,
      `AgentName` VARCHAR(191) NULL,
      `doc_type` VARCHAR(32) NOT NULL,
      `FileName` VARCHAR(255) NULL,
      `UploadTimestamp` DATETIME NOT NULL DEFAULT NOW(),
      `month_year` VARCHAR(32) NULL,
      `is_active` TINYINT(1) NOT NULL DEFAULT 1,
      PRIMARY KEY (`UploadID`),
      KEY `ix_uploads_agent_month` (`agent_code`,`month_year`),
      KEY `ix_uploads_doc` (`doc_type`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Statement
    op.execute("""
    CREATE TABLE IF NOT EXISTS `statement` (
      `statement_id` INT NOT NULL AUTO_INCREMENT,
      `upload_id` INT NULL,
      `agent_code` VARCHAR(64) NULL,
      `policy_no` VARCHAR(64) NULL,
      `holder` VARCHAR(191) NULL,
      `policy_type` VARCHAR(64) NULL,
      `pay_date` VARCHAR(32) NULL,
      `premium` DECIMAL(18,2) NULL,
      `com_rate` DECIMAL(9,4) NULL,
      `com_amt` DECIMAL(18,2) NULL,
      `inception` VARCHAR(32) NULL,
      `MONTH_YEAR` VARCHAR(32) NULL,
      `AGENT_LICENSE_NUMBER` VARCHAR(64) NULL,
      `period_date` DATE NULL,
      PRIMARY KEY (`statement_id`),
      KEY `ix_statement_agent_month` (`agent_code`,`MONTH_YEAR`),
      KEY `ix_statement_upload` (`upload_id`),
      KEY `ix_statement_policy` (`policy_no`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Schedule
    op.execute("""
    CREATE TABLE IF NOT EXISTS `schedule` (
      `schedule_id` INT NOT NULL AUTO_INCREMENT,
      `upload_id` INT NULL,
      `agent_code` VARCHAR(64) NULL,
      `agent_name` VARCHAR(191) NULL,
      `commission_batch_code` VARCHAR(64) NULL,
      `total_premiums` DECIMAL(18,2) NULL,
      `income` DECIMAL(18,2) NULL,
      `total_deductions` DECIMAL(18,2) NULL,
      `net_commission` DECIMAL(18,2) NULL,
      `siclase` DECIMAL(18,2) NULL,
      `premium_deduction` DECIMAL(18,2) NULL,
      `pensions` DECIMAL(18,2) NULL,
      `welfareko` DECIMAL(18,2) NULL,
      `month_year` VARCHAR(32) NULL,
      PRIMARY KEY (`schedule_id`),
      KEY `ix_schedule_agent_month` (`agent_code`,`month_year`),
      KEY `ix_schedule_upload` (`upload_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Terminated
    op.execute("""
    CREATE TABLE IF NOT EXISTS `terminated` (
      `terminated_id` INT NOT NULL AUTO_INCREMENT,
      `upload_id` INT NULL,
      `agent_code` VARCHAR(64) NULL,
      `policy_no` VARCHAR(64) NULL,
      `holder` VARCHAR(191) NULL,
      `policy_type` VARCHAR(64) NULL,
      `premium` DECIMAL(18,2) NULL,
      `status` VARCHAR(64) NULL,
      `reason` VARCHAR(191) NULL,
      `month_year` VARCHAR(32) NULL,
      `termination_date` VARCHAR(32) NULL,
      PRIMARY KEY (`terminated_id`),
      KEY `ix_terminated_agent_month` (`agent_code`,`month_year`),
      KEY `ix_terminated_upload` (`upload_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Active policies
    op.execute("""
    CREATE TABLE IF NOT EXISTS `active_policies` (
      `id` INT NOT NULL AUTO_INCREMENT,
      `agent_code` VARCHAR(64) NOT NULL,
      `policy_no` VARCHAR(64) NOT NULL,
      `policy_type` VARCHAR(64) NULL,
      `holder_name` VARCHAR(191) NULL,
      `inception_date` DATE NULL,
      `first_seen_date` DATE NULL,
      `last_seen_date` DATE NULL,
      `last_seen_month_year` VARCHAR(32) NULL,
      `last_premium` DECIMAL(18,2) NULL,
      `last_com_rate` DECIMAL(9,4) NULL,
      `status` VARCHAR(32) NULL,
      `consecutive_missing_months` INT NULL DEFAULT 0,
      PRIMARY KEY (`id`),
      UNIQUE KEY `ux_active_unique` (`agent_code`,`policy_no`),
      KEY `ix_active_last_month` (`last_seen_month_year`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Expected commissions
    op.execute("""
    CREATE TABLE IF NOT EXISTS `expected_commissions` (
      `id` INT NOT NULL AUTO_INCREMENT,
      `upload_id` INT NOT NULL,
      `agent_code` VARCHAR(64) NOT NULL,
      `policy_no` VARCHAR(64) NOT NULL,
      `policy_type` VARCHAR(64) NULL,
      `period` VARCHAR(7) NOT NULL, -- YYYY-MM
      `basis` VARCHAR(32) NULL,
      `percent` DECIMAL(9,4) NULL,
      `premium` DECIMAL(18,2) NULL,
      `expected_commission` DECIMAL(18,2) NULL,
      `created_at` DATETIME NOT NULL DEFAULT NOW(),
      PRIMARY KEY (`id`),
      UNIQUE KEY `ux_expected_unique` (`upload_id`,`agent_code`,`policy_no`,`period`,`basis`),
      KEY `ix_expected_upload` (`upload_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Monthly reports
    op.execute("""
    CREATE TABLE IF NOT EXISTS `monthly_reports` (
      `report_id` INT NOT NULL AUTO_INCREMENT,
      `agent_code` VARCHAR(64) NOT NULL,
      `agent_name` VARCHAR(191) NULL,
      `report_period` VARCHAR(20) NOT NULL,
      `upload_id` INT NULL,
      `policies_reported` INT NULL,
      `total_premium` DECIMAL(18,2) NULL,
      `total_commission_reported` DECIMAL(18,2) NULL,
      `total_commission_expected` DECIMAL(18,2) NULL,
      `variance_amount` DECIMAL(18,2) NULL,
      `variance_percentage` DECIMAL(9,2) NULL,
      `missing_policies_count` INT NULL,
      `commission_mismatches_count` INT NULL,
      `data_quality_issues_count` INT NULL,
      `terminated_policies_count` INT NULL,
      `overall_status` VARCHAR(32) NULL,
      `report_html` LONGTEXT NULL,
      `report_pdf_path` VARCHAR(255) NULL,
      `report_pdf_s3_url` VARCHAR(1024) NULL,
      `report_pdf_size_bytes` BIGINT NULL,
      `report_pdf_generated_at` DATETIME NULL,
      `generated_at` DATETIME NOT NULL,
      PRIMARY KEY (`report_id`),
      KEY `ix_reports_agent_period` (`agent_code`,`report_period`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Audit flags
    op.execute("""
    CREATE TABLE IF NOT EXISTS `audit_flags` (
      `id` INT NOT NULL AUTO_INCREMENT,
      `agent_code` VARCHAR(64) NOT NULL,
      `month_year` VARCHAR(32) NULL,
      `policy_no` VARCHAR(64) NULL,
      `flag_type` VARCHAR(64) NOT NULL,
      `severity` VARCHAR(16) NULL,
      `flag_detail` TEXT NULL,
      `expected_value` VARCHAR(191) NULL,
      `actual_value` VARCHAR(191) NULL,
      `created_at` DATETIME NOT NULL DEFAULT NOW(),
      `resolved` TINYINT(1) NOT NULL DEFAULT 0,
      `resolved_by` VARCHAR(64) NULL,
      `resolved_at` DATETIME NULL,
      `resolution_notes` TEXT NULL,
      PRIMARY KEY (`id`),
      KEY `ix_flags_agent_month` (`agent_code`,`month_year`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Discrepancies
    op.execute("""
    CREATE TABLE IF NOT EXISTS `discrepancies` (
      `id` INT NOT NULL AUTO_INCREMENT,
      `agent_code` VARCHAR(64) NOT NULL,
      `policy_no` VARCHAR(64) NULL,
      `period` VARCHAR(20) NULL,
      `month_year` VARCHAR(32) NULL,
      `diff_amount` DECIMAL(18,2) NULL,
      `statement_id` INT NULL,
      `severity` VARCHAR(16) NULL,
      `notes` TEXT NULL,
      `type` VARCHAR(64) NOT NULL,
      `created_at` DATETIME NOT NULL DEFAULT NOW(),
      PRIMARY KEY (`id`),
      UNIQUE KEY `ux_discrepancy` (`agent_code`,`policy_no`,`period`,`type`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Auth refresh tokens
    op.execute("""
    CREATE TABLE IF NOT EXISTS `auth_refresh_tokens` (
      `jti` VARCHAR(64) NOT NULL,
      `user_id` INT NOT NULL,
      `issued_at` DATETIME NOT NULL,
      `expires_at` DATETIME NOT NULL,
      `rotated_from` VARCHAR(64) NULL,
      `is_revoked` TINYINT(1) NOT NULL DEFAULT 0,
      `client_fingerprint` VARCHAR(255) NULL,
      `ip_address` VARCHAR(64) NULL,
      PRIMARY KEY (`jti`),
      KEY `ix_refresh_user` (`user_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # Auth token denylist
    op.execute("""
    CREATE TABLE IF NOT EXISTS `auth_token_denylist` (
      `jti` VARCHAR(64) NOT NULL,
      `reason` VARCHAR(64) NULL,
      `created_at` DATETIME NOT NULL,
      `expires_at` DATETIME NULL,
      PRIMARY KEY (`jti`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

    # CLI runs
    op.execute("""
    CREATE TABLE IF NOT EXISTS `cli_runs` (
      `run_id` INT NOT NULL AUTO_INCREMENT,
      `started_at` DATETIME NOT NULL,
      `ended_at` DATETIME NULL,
      `status` VARCHAR(20) NOT NULL,
      `message` TEXT NULL,
      `upload_id` INT NULL,
      `agent_code` VARCHAR(50) NULL,
      `report_period` VARCHAR(20) NULL,
      `expected_rows_computed` INT NULL,
      `expected_rows_inserted` INT NULL,
      `pdf_path` VARCHAR(255) NULL,
      PRIMARY KEY (`run_id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
    """)

def downgrade():
    op.execute("DROP TABLE IF EXISTS `cli_runs`;")
    op.execute("DROP TABLE IF EXISTS `auth_token_denylist`;")
    op.execute("DROP TABLE IF EXISTS `auth_refresh_tokens`;")
    op.execute("DROP TABLE IF EXISTS `discrepancies`;")
    op.execute("DROP TABLE IF EXISTS `audit_flags`;")
    op.execute("DROP TABLE IF EXISTS `monthly_reports`;")
    op.execute("DROP TABLE IF EXISTS `expected_commissions`;")
    op.execute("DROP TABLE IF EXISTS `active_policies`;")
    op.execute("DROP TABLE IF EXISTS `terminated`;")
    op.execute("DROP TABLE IF EXISTS `schedule`;")
    op.execute("DROP TABLE IF EXISTS `statement`;")
    op.execute("DROP TABLE IF EXISTS `uploads`;")
    op.execute("DROP TABLE IF EXISTS `agents`;")
    op.execute("DROP TABLE IF EXISTS `users`;")
