
# migrations/versions/20260129_0205_fix_auth_tokens_pk_and_indexing.py
from alembic import op
import sqlalchemy as sa

# Revision identifiers.
revision = "20260129_0205_fix_auth_tokens_pk_and_indexing"
down_revision = "20260127_0300_tokens_fk_and_invoker_views"
branch_labels = None
depends_on = None

def _exec(sql: str) -> None:
    for stmt in [s.strip() for s in (sql or "").split(";")]:
        if stmt:
            op.execute(sa.text(stmt))

def _scalar(sql: str, **p):
    return op.get_bind().execute(sa.text(sql), p).scalar()

def _has_index(table: str, name: str) -> bool:
    sql = """
    SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=:t AND INDEX_NAME=:i
    """
    return bool(_scalar(sql, t=table, i=name))

def _has_fk(table: str, name: str) -> bool:
    sql = """
    SELECT 1 FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
    WHERE CONSTRAINT_SCHEMA = DATABASE() AND TABLE_NAME=:t AND CONSTRAINT_NAME=:n
    """
    return bool(_scalar(sql, t=table, n=name))

def _pk_columns(table: str) -> str:
    sql = """
    SELECT GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS cols
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=:t AND INDEX_NAME='PRIMARY'
    GROUP BY INDEX_NAME
    """
    return (_scalar(sql, t=table) or "").upper()

def upgrade() -> None:
    # Ensure unique JTI even if PK is (id)
    if not _has_index("auth_refresh_tokens", "ux_tokens_jti"):
        _exec("CREATE UNIQUE INDEX `ux_tokens_jti` ON `auth_refresh_tokens`(`jti`)")

    # Ensure index on expires and revoked (helpful for cleanup)
    if not _has_index("auth_refresh_tokens", "ix_tokens_expires"):
        _exec("CREATE INDEX `ix_tokens_expires` ON `auth_refresh_tokens`(`expires_at`)")

    if not _has_index("auth_refresh_tokens", "ix_tokens_revoked"):
        _exec("CREATE INDEX `ix_tokens_revoked` ON `auth_refresh_tokens`(`is_revoked`)")

    # Ensure index on user_id
    if not _has_index("auth_refresh_tokens", "ix_tokens_user"):
        _exec("CREATE INDEX `ix_tokens_user` ON `auth_refresh_tokens`(`user_id`)")

    # Ensure FK to users (idempotent)
    if not _has_fk("auth_refresh_tokens", "fk_refresh_user"):
        _exec("""
        ALTER TABLE `auth_refresh_tokens`
        ADD CONSTRAINT `fk_refresh_user`
        FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
        ON DELETE CASCADE ON UPDATE CASCADE
        """)

def downgrade() -> None:
    # Keep safety indexes; only remove what we added, if present
    if _has_fk("auth_refresh_tokens", "fk_refresh_user"):
        _exec("ALTER TABLE `auth_refresh_tokens` DROP FOREIGN KEY `fk_refresh_user`")

    if _has_index("auth_refresh_tokens", "ix_tokens_user"):
        _exec("DROP INDEX `ix_tokens_user` ON `auth_refresh_tokens`")

    if _has_index("auth_refresh_tokens", "ix_tokens_revoked"):
        _exec("DROP INDEX `ix_tokens_revoked` ON `auth_refresh_tokens`")

    if _has_index("auth_refresh_tokens", "ix_tokens_expires"):
        _exec("DROP INDEX `ix_tokens_expires` ON `auth_refresh_tokens`")

    if _has_index("auth_refresh_tokens", "ux_tokens_jti"):
        _exec("DROP INDEX `ux_tokens_jti` ON `auth_refresh_tokens`")
