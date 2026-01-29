
# scripts/db/verify_auth_refresh_tokens.py
import os
import urllib.parse
import sqlalchemy as sa

def build_url():
    url = os.getenv("MYSQL_URL")
    if url and url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    if url:
        return url
    user = os.getenv("MYSQLUSER") or os.getenv("DB_USER")
    pw = os.getenv("MYSQLPASSWORD") or os.getenv("DB_PASSWORD")
    host = os.getenv("MYSQLHOST") or os.getenv("DB_HOST", "localhost")
    port = os.getenv("MYSQLPORT") or os.getenv("DB_PORT", "3306")
    db = os.getenv("MYSQLDATABASE") or os.getenv("DB_NAME", "railway")
    if user and pw and host and db:
        return f"mysql+pymysql://{urllib.parse.quote_plus(user)}:{urllib.parse.quote_plus(pw)}@{host}:{port}/{db}"
    raise SystemExit("Set MYSQL_URL or MYSQL* parts first")

def main():
    eng = sa.create_engine(build_url())
    with eng.connect() as conn:
        def q(sql, **p):
            return conn.execute(sa.text(sql), p)

        print("=== Structure: SHOW CREATE TABLE auth_refresh_tokens ===")
        sct = q("SHOW CREATE TABLE `auth_refresh_tokens`").fetchone()
        print(sct[1] if sct and len(sct) > 1 else "N/A")

        print("\n=== Indexes present? ===")
        for idx in ("ux_tokens_jti", "ix_tokens_expires", "ix_tokens_revoked", "ix_tokens_user"):
            row = q("""
                SELECT 1
                FROM INFORMATION_SCHEMA.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'auth_refresh_tokens'
                  AND INDEX_NAME = :i
                LIMIT 1
            """, i=idx).fetchone()
            print(f"{idx.ljust(20)} : {'OK' if row else 'MISSING'}")

        print("\n=== Foreign key fk_refresh_user present? ===")
        fk = q("""
            SELECT 1
            FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE()
              AND TABLE_NAME = 'auth_refresh_tokens'
              AND CONSTRAINT_NAME = 'fk_refresh_user'
            LIMIT 1
        """).fetchone()
        print(f"fk_refresh_user       : {'OK' if fk else 'MISSING'}")

if __name__ == "__main__":
    main()
