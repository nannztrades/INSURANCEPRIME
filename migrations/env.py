from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import Base from models
from src.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target_metadata from your models
target_metadata = Base. metadata

def get_url():
    """
    Build DATABASE_URL from Railway environment variables. 
    Railway provides:  MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, MYSQLDATABASE
    """
    # Try Railway-style variables first
    host = os.getenv("MYSQLHOST")
    port = os.getenv("MYSQLPORT", "3306")
    user = os.getenv("MYSQLUSER")
    password = os.getenv("MYSQLPASSWORD")
    database = os.getenv("MYSQLDATABASE")
    
    # Fallback to standard DB_* variables
    if not all([host, user, password, database]):
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT", "3306")
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASSWORD")
        database = os.getenv("DB_NAME")
    
    # Final fallback:  DATABASE_URL (if provided as single string)
    if not all([host, user, password, database]):
        return os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    
    # Build MySQL URL with pymysql driver
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

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
    configuration["sqlalchemy.url"] = get_url()
    
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