# src/ingestion/db.py
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    """Get a raw pymysql connection for legacy code."""
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    database = os.getenv("DB_NAME", "railway")
    port = int(os.getenv("DB_PORT", "3306"))
    
    # ✅ Type-safe:  Validate required env vars
    if not user or not password: 
        raise ValueError("DB_USER and DB_PASSWORD must be set in environment variables")
    
    return pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=port,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor
    )