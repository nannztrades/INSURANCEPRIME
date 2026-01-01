# migrations/env.py
from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ Import Base from src.models (NOT src.ingestion.models)
try:
    from src.models import Base
    target_metadata = Base.metadata
except ImportError as e:
    print(f"WARNING: Could not import Base metadata: {e}")
    target_metadata = None


def get_url() -> str:
    """Get database URL from environment variables."""
    # Railway provides MYSQL_URL
    url = os.getenv("MYSQL_URL")
    if url:
        # Railway uses mysql:// but we need mysql+pymysql://
        if url.startswith("mysql://"):
            url = url.replace("mysql://", "mysql+pymysql://", 1)
        return url
    
    # Fallback:  construct from individual vars
    user = os.getenv("MYSQLUSER") or os.getenv("DB_USER")
    password = os.getenv("MYSQLPASSWORD") or os.getenv("DB_PASSWORD")
    host = os.getenv("MYSQLHOST") or os.getenv("DB_HOST", "localhost")
    port = os.getenv("MYSQLPORT") or os.getenv("DB_PORT", "3306")
    database = os.getenv("MYSQLDATABASE") or os.getenv("DB_NAME", "railway")
    
    if user and password and host and database:
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    
    # Final fallback:  alembic. ini (local dev only)
    return config.get_main_option("sqlalchemy.url") or ""


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    url = get_url()
    
    # ✅ Type-safe:  Ensure url is not None
    if not url:
        raise ValueError("Database URL not configured.  Set MYSQL_URL or DB_* environment variables.")
    
    configuration["sqlalchemy.url"] = url
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context. configure(
            connection=connection,
            target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()