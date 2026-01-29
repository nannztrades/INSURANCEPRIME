
import os, urllib.parse, sqlalchemy as sa

def build_url():
    url = os.getenv("MYSQL_URL")
    if url and url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    if url:
        return url
    user = os.getenv("MYSQLUSER") or os.getenv("DB_USER")
    pw   = os.getenv("MYSQLPASSWORD") or os.getenv("DB_PASSWORD")
    host = os.getenv("MYSQLHOST") or os.getenv("DB_HOST", "localhost")
    port = os.getenv("MYSQLPORT") or os.getenv("DB_PORT", "3306")
    db   = os.getenv("MYSQLDATABASE") or os.getenv("DB_NAME", "railway")
    if user and pw and host and db:
        return f"mysql+pymysql://{urllib.parse.quote_plus(user)}:{urllib.parse.quote_plus(pw)}@{host}:{port}/{db}"
    raise SystemExit("Set MYSQL_URL or MYSQL* pieces first")

def fetch_all(conn, sql, **p): return conn.execute(sa.text(sql), p).mappings().all()
def scalar(conn, sql, **p):    return conn.execute(sa.text(sql), p).scalar()

def has_col(conn, t, c):
    return bool(fetch_all(conn, f"SHOW COLUMNS FROM `{t}` LIKE :c", c=c))

def dtype(conn, t, c):
    return (scalar(conn, """
        SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME=:t AND COLUMN_NAME=:c
    """, t=t, c=c) or "").lower()

def has_idx(conn, t, name):
    return bool(fetch_all(conn, f"SHOW INDEX FROM `{t}` WHERE Key_name=:k", k=name))

def has_fk(conn, t, name):
    db = scalar(conn, "SELECT DATABASE()")
    return bool(fetch_all(conn, """
        SELECT 1 FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA=:db AND TABLE_NAME=:t AND CONSTRAINT_NAME=:n
    """, db=db, t=t, n=name))

def len_ver(conn):
    return scalar(conn, """
        SELECT CHARACTER_MAXIMUM_LENGTH
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=DATABASE()
          AND TABLE_NAME='alembic_version' AND COLUMN_NAME='version_num'
    """)

def main():
    eng = sa.create_engine(build_url())
    with eng.connect() as conn:
        print("alembic_version.version_num length:", len_ver(conn))
        checks = [
            ("statement.receipt_no exists", has_col(conn, "statement", "receipt_no")),
            ("statement.pay_date is DATE", dtype(conn, "statement", "pay_date") == "date"),
            ("FK fk_statement_upload",   has_fk(conn, "statement",  "fk_statement_upload")),
            ("FK fk_schedule_upload",    has_fk(conn, "schedule",   "fk_schedule_upload")),
            ("FK fk_terminated_upload",  has_fk(conn, "terminated", "fk_terminated_upload")),
            ("FK fk_users_agent_code_agents", has_fk(conn, "users", "fk_users_agent_code_agents")),
            ("UX ux_uploads_active_tuple", has_idx(conn, "uploads", "ux_uploads_active_tuple")),
            ("IDX ix_statement_agent_month_pol",  has_idx(conn, "statement", "ix_statement_agent_month_pol")),
            ("IDX ix_terminated_agent_month_pol", has_idx(conn, "terminated","ix_terminated_agent_month_pol")),
            ("IDX ix_expected_upload",            has_idx(conn, "expected_commissions","ix_expected_upload")),
        ]
        w = max(len(n) for n,_ in checks)
        for name, ok in checks:
            print(f"{name.ljust(w)} : {'OK' if ok else 'MISSING'}")

if __name__ == "__main__":
    main()
