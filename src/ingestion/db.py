
# src/ingestion/db.py
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "insurancelocal"),
        port=int(os.getenv("DB_PORT", "3306")),
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor
    )
