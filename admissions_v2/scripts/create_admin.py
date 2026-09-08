"""Create an administrator locally, without public signup or password arguments."""
from __future__ import annotations

import argparse
from getpass import getpass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Administrator")
    parser.add_argument("--local-demo", action="store_true", help="Use the isolated local demo database.")
    args = parser.parse_args()
    if args.local_demo:
        import os
        from scripts.local_demo import DEFAULT_DEMO_ROOT, demo_environment
        env = demo_environment(DEFAULT_DEMO_ROOT, dict(os.environ))
        os.environ.clear()
        os.environ.update(env)
    from scripts import db
    from scripts.student_accounts import RegistrationRequest

    password = getpass("New administrator password (8+ characters): ")
    if password != getpass("Repeat password: "):
        raise SystemExit("Passwords do not match. No account created.")
    payload = RegistrationRequest(email=args.email, display_name=args.name, password=password)
    db.init_db()
    conn = db.get_conn()
    try:
        cur = db._execute(conn,
            "INSERT INTO app_users (email,display_name,role,password_hash,status) "
            f"VALUES ({','.join([db._ph()] * 5)}) ON CONFLICT(email) DO NOTHING",
            (payload.email, payload.display_name, "owner_admin", db._hash_password(password), "active"))
        if cur.rowcount != 1:
            raise SystemExit("Account already exists. No account changed.")
        conn.commit()
    finally:
        conn.close()
    print("Administrator created. Sign in using its email address.")


if __name__ == "__main__":
    main()
