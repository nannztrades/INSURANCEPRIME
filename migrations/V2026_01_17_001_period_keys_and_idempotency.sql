
-- migrations/V2026_01_17_001_period_keys_and_idempotency.sql
-- Safe, additive DDL for local dev
-- MySQL 8+ is assumed.

SET NAMES utf8mb4;
SET time_zone = '+00:00';

-- 1) UPLOADS: canonical month key
ALTER TABLE `uploads`
  ADD COLUMN `period_key` VARCHAR(7)
    GENERATED ALWAYS AS (
      DATE_FORMAT(STR_TO_DATE(CONCAT('01 ', `month_year`), '%d %b %Y'), '%Y-%m')
    ) STORED,
  ADD INDEX `ix_u_agent_period_doc_act` (`agent_code`, `period_key`, `doc_type`, `is_active`);

-- 2) STATEMENT: canonical month key + idempotency hash
ALTER TABLE `statement`
  ADD COLUMN `period_key` VARCHAR(7)
    GENERATED ALWAYS AS (
      DATE_FORMAT(STR_TO_DATE(CONCAT('01 ', `MONTH_YEAR`), '%d %b %Y'), '%Y-%m')
    ) STORED,
  ALGORITHM=INPLACE, LOCK=NONE
;

-- For idempotency: generated unique hash across the row's identity fields
ALTER TABLE `statement`
  ADD COLUMN `unique_id_hash` CHAR(64)
    GENERATED ALWAYS AS (
      UPPER(
        SHA2(
          CONCAT_WS('|',
            COALESCE(`agent_code`, ''),
            COALESCE(`policy_no`, ''),
            DATE_FORMAT(COALESCE(`pay_date`, CAST('1970-01-01' AS DATE)), '%Y-%m-%d'),
            -- Normalize numerics to 2dp consistently
            LPAD(REPLACE(ROUND(COALESCE(`premium`, 0.00), 2), ',', ''), 1, ''),
            LPAD(REPLACE(ROUND(COALESCE(`com_amt`, 0.00), 2), ',', ''), 1, ''),
            COALESCE(`receipt_no`, ''),
            DATE_FORMAT(STR_TO_DATE(CONCAT('01 ', `MONTH_YEAR`), '%d %b %Y'), '%Y-%m')
          ),
          256
        )
      )
    ) STORED,
  ADD UNIQUE KEY `ux_statement_unique_id_hash` (`unique_id_hash`),
  ADD INDEX `ix_s_agent_period` (`agent_code`, `period_key`);

-- 3) SCHEDULE: canonical month key + helpful index
ALTER TABLE `schedule`
  ADD COLUMN `period_key` VARCHAR(7)
    GENERATED ALWAYS AS (
      DATE_FORMAT(STR_TO_DATE(CONCAT('01 ', `month_year`), '%d %b %Y'), '%Y-%m')
    ) STORED,
  ADD INDEX `ix_sched_agent_period` (`agent_code`, `period_key`);

-- 4) TERMINATED: canonical month key + helpful index
ALTER TABLE `terminated`
  ADD COLUMN `period_key` VARCHAR(7)
    GENERATED ALWAYS AS (
      DATE_FORMAT(STR_TO_DATE(CONCAT('01 ', `month_year`), '%d %b %Y'), '%Y-%m')
    ) STORED,
  ADD INDEX `ix_term_agent_period` (`agent_code`, `period_key`);
