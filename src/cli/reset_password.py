
# src/cli/reset_password.py
from __future__ import annotations
import argparse
from src.ingestion.db import get_conn
from src.services.auth_service import hash_password

def main():
    ap = argparse.ArgumentParser(description="Reset a user's password to Argon2")
    ap.add_argument("--user-id", type=int, required=True, help="User ID in the `users` table")
    ap.add_argument("--new-password", type=str, required=True, help="New plaintext password")
    args = ap.parse_args()

    hashed = hash_password(args.new_password)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE `users` SET `password_hash`=%s, `is_active`=1 WHERE `id`=%s",
                (hashed, args.user_id),
            )
        conn.commit()
        print(f"[OK] Password reset for user_id={args.user_id} (argon2).")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
