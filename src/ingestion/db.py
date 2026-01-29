
# src/ingestion/db.py
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse, unquote

import pymysql
from dotenv import load_dotenv

# Load .env if present (local/dev). In production (e.g., Railway), envs are already present.
load_dotenv()

# -----------------------------------------------------------------------------
# Optional SQL echo (DB_ECHO=1) — logs SQL text, parameters, and elapsed time.
# -----------------------------------------------------------------------------
_DB_ECHO = bool(int(os.getenv("DB_ECHO", "0")))

class LoggingCursor(pymysql.cursors.DictCursor):
    """A DictCursor that logs SQL, params, and elapsed time when DB_ECHO=1."""
    def execute(self, query, args=None):
        if _DB_ECHO:
            echo_logger = logging.getLogger("pymysql.echo")
            echo_logger.debug("SQL: %s", query)
            if args:
                echo_logger.debug("ARGS: %r", args)
            start = time.perf_counter()
            try:
                return super().execute(query, args)
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000.0
                echo_logger.debug("TIME: %.2f ms", elapsed_ms)
        return super().execute(query, args)

def _configure_echo_logging() -> None:
    """Configure lightweight logging if DB_ECHO=1 (idempotent)."""
    if not _DB_ECHO:
        return
    # Avoid clobbering app-wide logging formats if already configured
    echo_logger = logging.getLogger("pymysql.echo")
    if not echo_logger.handlers:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(levelname)s %(name)s: %(message)s",
        )
        logging.getLogger("pymysql").setLevel(logging.DEBUG)
        echo_logger.setLevel(logging.DEBUG)

# -----------------------------------------------------------------------------
# URL parsing and env precedence
# -----------------------------------------------------------------------------
def _parse_mysql_url(url: str) -> Dict[str, Any]:
    """
    Parse a MySQL URL into PyMySQL connection kwargs.
    Supports:
      - mysql://user:pass@host:3306/dbname
      - mysql+pymysql://user:pass@host/dbname
      - user:pass@host:3306/dbname (scheme implied)
    Returns: dict(host, user, password, database, port)
    """
    raw = (url or "").strip()
    if not raw:
        raise ValueError("MYSQL_URL is empty")
    # Normalize scheme to mysql:// for parsing if mysql+pymysql:// is used
    if raw.startswith("mysql+pymysql://"):
        raw = raw.replace("mysql+pymysql://", "mysql://", 1)
    parsed = urlparse(raw) if "://" in raw else urlparse("mysql://" + raw)
    if parsed.scheme not in {"mysql"}:
        # Best-effort normalize any unknown scheme to mysql
        parsed = urlparse("mysql://" + raw.split("://", 1)[-1])

    user = unquote(parsed.username or "") or None
    password = unquote(parsed.password or "") or None
    host = parsed.hostname or "localhost"
    try:
        port = int(parsed.port) if parsed.port is not None else 3306
    except ValueError:
        port = 3306
    # Path is like "/dbname"
    database = parsed.path[1:] if parsed.path and len(parsed.path) > 1 else None

    return {
        "host": host,
        "user": user,
        "password": password,
        "database": database,
        "port": port,
    }

def _build_pymysql_kwargs(
    host: str,
    user: str,
    password: str,
    database: Optional[str],
    port: int,
) -> Dict[str, Any]:
    """
    Build consistent kwargs for pymysql.connect(), applying optional tuning from env:
      - DB_CONNECT_TIMEOUT (seconds, int)
      - DB_READ_TIMEOUT (seconds, int)
      - DB_WRITE_TIMEOUT (seconds, int)
      - DB_AUTOCOMMIT (0/1)
      - DB_CHARSET (default 'utf8mb4')
    """
    # Optional timeouts
    def _to_int(val: Optional[str], default: Optional[int]) -> Optional[int]:
        try:
            return int(val) if val is not None else default
        except ValueError:
            return default

    connect_timeout = _to_int(os.getenv("DB_CONNECT_TIMEOUT"), None)
    read_timeout = _to_int(os.getenv("DB_READ_TIMEOUT"), None)
    write_timeout = _to_int(os.getenv("DB_WRITE_TIMEOUT"), None)

    autocommit = bool(int(os.getenv("DB_AUTOCOMMIT", "0")))
    charset = os.getenv("DB_CHARSET", "utf8mb4")

    kwargs: Dict[str, Any] = {
        "host": host,
        "user": user,
        "password": password,
        "database": database or "",
        "port": port,
        "charset": charset,
        "autocommit": autocommit,
        "cursorclass": LoggingCursor if _DB_ECHO else pymysql.cursors.DictCursor,
    }
    if connect_timeout is not None:
        kwargs["connect_timeout"] = connect_timeout
    if read_timeout is not None:
        kwargs["read_timeout"] = read_timeout
    if write_timeout is not None:
        kwargs["write_timeout"] = write_timeout

    # Optional SSL support via env (common in hosted MySQL)
    ssl_ca = os.getenv("MYSQL_SSL_CA")
    if ssl_ca:
        kwargs["ssl"] = {"ca": ssl_ca}

    return kwargs

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def get_conn():
    """
    Return a new PyMySQL connection.

    Order of precedence (to match migrations/env.py and hosted envs):
      1) MYSQL_URL (e.g., mysql://user:pass@host:3306/db)
      2) Railway-style MYSQL* vars: MYSQLUSER, MYSQLPASSWORD, MYSQLHOST, MYSQLPORT, MYSQLDATABASE
      3) DB_* vars: DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME

    Optional:
      - DB_ECHO=1 to enable SQL echo (LoggingCursor)
      - DB_CONNECT_TIMEOUT, DB_READ_TIMEOUT, DB_WRITE_TIMEOUT (seconds)
      - DB_AUTOCOMMIT=0/1 (default 0)
      - DB_CHARSET (default utf8mb4)
      - MYSQL_SSL_CA (path to CA bundle for SSL)
    """
    _configure_echo_logging()

    # 1) Full URL
    mysql_url = os.getenv("MYSQL_URL")
    if mysql_url:
        params = _parse_mysql_url(mysql_url)
        if not params.get("user") or not params.get("password"):
            raise ValueError("MYSQL_URL must include username and password")
        if not params.get("database"):
            raise ValueError("MYSQL_URL must include a database name in the path")
        kwargs = _build_pymysql_kwargs(
            host=params["host"],
            user=params["user"],
            password=params["password"],
            database=params["database"],
            port=params["port"],
        )
        return pymysql.connect(**kwargs)

    # 2) Railway-style MYSQL* environment variables
    user = os.getenv("MYSQLUSER")
    password = os.getenv("MYSQLPASSWORD")
    host = os.getenv("MYSQLHOST")
    database = os.getenv("MYSQLDATABASE")
    port_env = os.getenv("MYSQLPORT")

    # 3) Fallback to DB_*
    user = user or os.getenv("DB_USER")
    password = password or os.getenv("DB_PASSWORD")
    host = host or os.getenv("DB_HOST", "localhost")
    database = database or os.getenv("DB_NAME", "railway")
    port_env = port_env or os.getenv("DB_PORT", "3306")

    try:
        port = int(port_env or "3306")
    except ValueError:
        port = 3306

    # Validate creds
    if not user or not password:
        raise ValueError(
            "Database credentials not set. Provide either MYSQL_URL or "
            "MYSQL* / DB_* environment variables (user and password are required)."
        )

    kwargs = _build_pymysql_kwargs(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
    )
    return pymysql.connect(**kwargs)

# -----------------------------------------------------------------------------
# Optional quick self-test (run: python -m src.ingestion.db)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            row = cur.fetchone()
        conn.close()
        print("DB OK:", row)
    except Exception as e:
        print("DB ERROR:", type(e).__name__, str(e))
        raise
