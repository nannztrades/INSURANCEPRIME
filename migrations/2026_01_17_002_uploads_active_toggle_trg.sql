
-- migrations/V2026_01_17_002_uploads_active_toggle_trg.sql
-- Ensure mutual exclusivity of active uploads per (agent_code, period_key, doc_type).

DROP TRIGGER IF EXISTS `trg_uploads_after_insert_active_toggle`;
DELIMITER $$
CREATE TRIGGER `trg_uploads_after_insert_active_toggle`
AFTER INSERT ON `uploads`
FOR EACH ROW
BEGIN
  -- First, deactivate any other active uploads for same agent + month + type
  UPDATE `uploads`
     SET `is_active` = 0
   WHERE `agent_code` = NEW.`agent_code`
     AND `period_key` = NEW.`period_key`
     AND `doc_type`   = NEW.`doc_type`
     AND `UploadID`  <> NEW.`UploadID`
     AND `is_active`  = 1;

  -- Then, ensure this new row is active
  UPDATE `uploads`
     SET `is_active` = 1
   WHERE `UploadID` = NEW.`UploadID`;
END$$
DELIMITER ;
``
