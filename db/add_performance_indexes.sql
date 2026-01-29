-- db/add_performance_indexes.sql

-- Index period_key columns (used in WHERE clauses)
CREATE INDEX IF NOT EXISTS ix_statement_period_key 
ON statement(period_key);

CREATE INDEX IF NOT EXISTS ix_schedule_period_key 
ON schedule(period_key);

CREATE INDEX IF NOT EXISTS ix_terminated_period_key 
ON terminated(period_key);

CREATE INDEX IF NOT EXISTS ix_uploads_period_key 
ON uploads(period_key);

-- Composite index for missing policies query
CREATE INDEX IF NOT EXISTS ix_statement_agent_period_policy 
ON statement(agent_code, period_key, policy_no);

-- Index for terminated lookup
CREATE INDEX IF NOT EXISTS ix_terminated_agent_period_policy 
ON terminated(agent_code, period_key, policy_no);