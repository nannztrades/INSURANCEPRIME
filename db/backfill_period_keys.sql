-- db/backfill_period_keys.sql
-- Run BEFORE deploying new code to ensure all data is YYYY-MM

SET @old_fk = @@FOREIGN_KEY_CHECKS;
SET FOREIGN_KEY_CHECKS = 0;

-- Helper function to normalize month_year
DELIMITER //
CREATE TEMPORARY FUNCTION normalize_period(label VARCHAR(50))
RETURNS VARCHAR(7)
DETERMINISTIC
BEGIN
    DECLARE result VARCHAR(7);
    DECLARE month_num INT;
    
    -- Already YYYY-MM
    IF label REGEXP '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN
        RETURN label;
    END IF;
    
    -- COM_JUN_2025
    IF label REGEXP 'COM[_-]([A-Z]{3})[_-]([0-9]{4})' THEN
        SET month_num = CASE SUBSTRING_INDEX(SUBSTRING_INDEX(label, '_', -2), '_', 1)
            WHEN 'JAN' THEN 1 WHEN 'FEB' THEN 2 WHEN 'MAR' THEN 3
            WHEN 'APR' THEN 4 WHEN 'MAY' THEN 5 WHEN 'JUN' THEN 6
            WHEN 'JUL' THEN 7 WHEN 'AUG' THEN 8 WHEN 'SEP' THEN 9
            WHEN 'OCT' THEN 10 WHEN 'NOV' THEN 11 WHEN 'DEC' THEN 12
            ELSE NULL
        END;
        IF month_num IS NOT NULL THEN
            RETURN CONCAT(
                SUBSTRING_INDEX(label, '_', -1),
                '-',
                LPAD(month_num, 2, '0')
            );
        END IF;
    END IF;
    
    -- Jun 2025
    IF label REGEXP '^[A-Za-z]{3} [0-9]{4}$' THEN
        SET month_num = CASE UPPER(SUBSTRING_INDEX(label, ' ', 1))
            WHEN 'JAN' THEN 1 WHEN 'FEB' THEN 2 WHEN 'MAR' THEN 3
            WHEN 'APR' THEN 4 WHEN 'MAY' THEN 5 WHEN 'JUN' THEN 6
            WHEN 'JUL' THEN 7 WHEN 'AUG' THEN 8 WHEN 'SEP' THEN 9
            WHEN 'SEPT' THEN 9 WHEN 'OCT' THEN 10 WHEN 'NOV' THEN 11
            WHEN 'DEC' THEN 12 ELSE NULL
        END;
        IF month_num IS NOT NULL THEN
            RETURN CONCAT(
                SUBSTRING_INDEX(label, ' ', -1),
                '-',
                LPAD(month_num, 2, '0')
            );
        END IF;
    END IF;
    
    -- YYYY/MM
    IF label REGEXP '^[0-9]{4}/[0-9]{1,2}$' THEN
        RETURN CONCAT(
            SUBSTRING_INDEX(label, '/', 1),
            '-',
            LPAD(SUBSTRING_INDEX(label, '/', -1), 2, '0')
        );
    END IF;
    
    RETURN NULL;  -- Unparseable
END//
DELIMITER ;

-- Backfill statement
UPDATE statement
SET MONTH_YEAR = normalize_period(MONTH_YEAR)
WHERE MONTH_YEAR IS NOT NULL
  AND normalize_period(MONTH_YEAR) IS NOT NULL;

-- Backfill schedule
UPDATE schedule
SET month_year = normalize_period(month_year)
WHERE month_year IS NOT NULL
  AND normalize_period(month_year) IS NOT NULL;

-- Backfill terminated
UPDATE terminated
SET month_year = normalize_period(month_year)
WHERE month_year IS NOT NULL
  AND normalize_period(month_year) IS NOT NULL;

-- Backfill uploads
UPDATE uploads
SET month_year = normalize_period(month_year)
WHERE month_year IS NOT NULL
  AND normalize_period(month_year) IS NOT NULL;

-- Backfill monthly_reports
UPDATE monthly_reports
SET report_period = normalize_period(report_period)
WHERE report_period IS NOT NULL
  AND normalize_period(report_period) IS NOT NULL;

-- Backfill cli_runs
UPDATE cli_runs
SET report_period = normalize_period(report_period)
WHERE report_period IS NOT NULL
  AND normalize_period(report_period) IS NOT NULL;

-- Backfill active_policies
UPDATE active_policies
SET last_seen_month_year = normalize_period(last_seen_month_year)
WHERE last_seen_month_year IS NOT NULL
  AND normalize_period(last_seen_month_year) IS NOT NULL;

-- Backfill audit_flags
UPDATE audit_flags
SET month_year = normalize_period(month_year)
WHERE month_year IS NOT NULL
  AND normalize_period(month_year) IS NOT NULL;

-- Backfill discrepancies
UPDATE discrepancies
SET period = normalize_period(period),
    month_year = normalize_period(month_year)
WHERE (period IS NOT NULL AND normalize_period(period) IS NOT NULL)
   OR (month_year IS NOT NULL AND normalize_period(month_year) IS NOT NULL);

DROP TEMPORARY FUNCTION normalize_period;

SET FOREIGN_KEY_CHECKS = @old_fk;

-- Verify (should return 0)
SELECT 
    'statement' AS tbl, COUNT(*) AS bad_count
FROM statement
WHERE MONTH_YEAR IS NOT NULL 
  AND MONTH_YEAR NOT REGEXP '^[0-9]{4}-(0[1-9]|1[0-2])$'
UNION ALL
SELECT 'schedule', COUNT(*)
FROM schedule
WHERE month_year IS NOT NULL 
  AND month_year NOT REGEXP '^[0-9]{4}-(0[1-9]|1[0-2])$'
UNION ALL
SELECT 'terminated', COUNT(*)
FROM terminated
WHERE month_year IS NOT NULL 
  AND month_year NOT REGEXP '^[0-9]{4}-(0[1-9]|1[0-2])$'
UNION ALL
SELECT 'uploads', COUNT(*)
FROM uploads
WHERE month_year IS NOT NULL 
  AND month_year NOT REGEXP '^[0-9]{4}-(0[1-9]|1[0-2])$';