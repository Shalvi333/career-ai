from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

import requests

DB_PATH = Path(__file__).parent / "data" / "career_ai_demo.db"


def supabase_http_session() -> requests.Session:
    """Reuse Supabase HTTPS connections across Streamlit reruns."""
    try:
        import streamlit as st

        @st.cache_resource(show_spinner=False)
        def _cached_session() -> requests.Session:
            return requests.Session()

        return _cached_session()
    except Exception:
        # The database module can also be used without Streamlit in local tests.
        return requests.Session()


def supabase_config() -> tuple[str, str] | None:
    """Read cloud-database settings without ever exposing their values in the UI."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SECRET_KEY", "").strip()

    try:
        import streamlit as st

        url = url or str(st.secrets.get("SUPABASE_URL", "")).strip()
        key = key or str(
            st.secrets.get(
                "SUPABASE_SECRET_KEY",
                st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", ""),
            )
        ).strip()
    except Exception:
        # Streamlit secrets are optional while developing locally.
        pass

    # Avoid a cryptic urllib crash when a key is accidentally pasted into the
    # URL field or the protocol is missing.
    parsed_url = urlparse(url)
    if (
        url
        and key
        and parsed_url.scheme in {"https", "http"}
        and parsed_url.netloc.endswith(".supabase.co")
        and not parsed_url.netloc.startswith("sb_")
    ):
        return url.rstrip("/"), key
    return None


def using_supabase() -> bool:
    return supabase_config() is not None


def _supabase_request(
    method: str,
    endpoint: str,
    payload: dict | list | None = None,
    extra_headers: dict[str, str] | None = None,
):
    """Make a small PostgREST request to Supabase using its server-only secret."""
    config = supabase_config()
    if not config:
        return None, "Cloud storage is not configured yet."

    base_url, secret_key = config
    headers = {
        "apikey": secret_key,
        "Authorization": f"Bearer {secret_key}",
        "Accept": "application/json",
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    try:
        response = supabase_http_session().request(
            method,
            f"{base_url}/rest/v1/{endpoint}",
            json=payload,
            headers=headers,
            timeout=(4, 10),
        )
        if response.status_code >= 400:
            return None, (
                f"Cloud database request failed ({response.status_code}): "
                f"{response.text}"
            )
        return (response.json() if response.content else None), ""
    except (requests.RequestException, ValueError):
        return None, "Cloud database could not be reached. Please try again."


def friendly_cloud_error(error: str) -> str:
    """Turn a technical cloud failure into a useful, safe message for students."""
    lowered = error.lower()
    if "404" in error or "42p01" in lowered or "relation" in lowered:
        return "Your Supabase tables are missing in this project. Please run the setup SQL once more."
    if "401" in error or "403" in error or "apikey" in lowered or "jwt" in lowered:
        return "Your Supabase secret key is not accepted. Check the secret key in secrets.toml."
    if "could not be reached" in lowered:
        return "Your Supabase project could not be reached. Check that the project is active and your internet is connected."
    return "We could not create your cloud account right now. Please try again."


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialise_database():
    # Supabase already owns its tables. SQLite is used only when cloud settings
    # are absent, which keeps the app easy to run locally too.
    if using_supabase():
        return

    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                student_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS student_states (
                email TEXT PRIMARY KEY,
                state_json TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email) REFERENCES users(email)
            )
        """)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        310000,
    ).hex()


def create_user(name: str, email: str, password: str):
    email = email.strip().lower()
    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)

    if using_supabase():
        student_id = str(uuid.uuid4())
        user = {
            "student_id": student_id,
            "name": name.strip().title(),
            "email": email,
            "password_salt": salt,
            "password_hash": password_hash,
        }
        _, error = _supabase_request(
            "POST",
            "career_ai_users",
            user,
            {"Prefer": "return=minimal"},
        )
        if error:
            if "409" in error or "duplicate" in error.lower() or "23505" in error:
                return None, "An account with this email already exists. Please log in instead."
            return None, friendly_cloud_error(error)

        _, state_error = _supabase_request(
            "POST",
            "career_ai_states",
            {"email": email, "state_json": {}},
            {"Prefer": "return=minimal"},
        )
        if state_error:
            # The account exists, so do not show a false failure to the student.
            pass
        return {"student_id": student_id, "name": user["name"], "email": email}, ""

    try:
        with get_connection() as connection:
            student_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO users
                (student_id, name, email, password_salt, password_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                (student_id, name.strip().title(), email, salt, password_hash),
            )
            connection.execute(
                "INSERT INTO student_states (email, state_json) VALUES (?, ?)",
                (email, "{}"),
            )

        return {
            "student_id": student_id,
            "name": name.strip().title(),
            "email": email,
        }, ""

    except sqlite3.IntegrityError:
        return None, "An account with this email already exists. Please log in instead."


def authenticate_user(email: str, password: str):
    email = email.strip().lower()

    if using_supabase():
        encoded_email = quote(email, safe="")
        users, error = _supabase_request(
            "GET",
            "career_ai_users?email=eq."
            f"{encoded_email}&select=student_id,name,email,password_salt,password_hash&limit=1",
        )
        if error:
            return None, "We could not reach your saved account right now. Please try again."
        user = users[0] if users else None
        if not user:
            return None, "No account was found with this email. Please create an account first."

        entered_hash = hash_password(password, user["password_salt"])
        if not hmac.compare_digest(entered_hash, user["password_hash"]):
            return None, "Incorrect password. Please try again."
        return {
            "student_id": user["student_id"],
            "name": user["name"],
            "email": user["email"],
        }, ""

    with get_connection() as connection:
        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if not user:
        return None, "No account was found with this email. Please create an account first."

    entered_hash = hash_password(password, user["password_salt"])

    if not hmac.compare_digest(entered_hash, user["password_hash"]):
        return None, "Incorrect password. Please try again."

    return {
        "student_id": user["student_id"],
        "name": user["name"],
        "email": user["email"],
    }, ""


def get_user_by_student_id(student_id: str):
    """Load the small public account record used by a signed remember token.

    This deliberately never returns password fields. It is only used after a
    signed session token has been verified by the Streamlit app.
    """
    clean_id = str(student_id).strip()
    if not clean_id:
        return None

    if using_supabase():
        encoded_id = quote(clean_id, safe="")
        users, error = _supabase_request(
            "GET",
            "career_ai_users?student_id=eq."
            f"{encoded_id}&select=student_id,name,email&limit=1",
        )
        if error or not users:
            return None
        user = users[0]
        return {
            "student_id": user["student_id"],
            "name": user["name"],
            "email": user["email"],
        }

    with get_connection() as connection:
        user = connection.execute(
            "SELECT student_id, name, email FROM users WHERE student_id = ?",
            (clean_id,),
        ).fetchone()
    if not user:
        return None
    return {
        "student_id": user["student_id"],
        "name": user["name"],
        "email": user["email"],
    }


def update_user_password(email: str, current_password: str, new_password: str):
    """Safely replace a signed-in user's password after verifying the old one."""
    clean_email = email.strip().lower()

    if using_supabase():
        encoded_email = quote(clean_email, safe="")
        users, error = _supabase_request(
            "GET",
            "career_ai_users?email=eq."
            f"{encoded_email}&select=password_salt,password_hash&limit=1",
        )
        if error or not users:
            return False, "Your account could not be found. Please log in again."
        user = users[0]
        current_hash = hash_password(current_password, user["password_salt"])
        if not hmac.compare_digest(current_hash, user["password_hash"]):
            return False, "Your current password is incorrect."

        new_salt = secrets.token_hex(16)
        _, error = _supabase_request(
            "PATCH",
            f"career_ai_users?email=eq.{encoded_email}",
            {"password_salt": new_salt, "password_hash": hash_password(new_password, new_salt)},
            {"Prefer": "return=minimal"},
        )
        return (not error), ("" if not error else "We could not update your password right now.")

    with get_connection() as connection:
        user = connection.execute(
            "SELECT password_salt, password_hash FROM users WHERE email = ?",
            (clean_email,),
        ).fetchone()

        if not user:
            return False, "Your account could not be found. Please log in again."
        current_hash = hash_password(current_password, user["password_salt"])
        if not hmac.compare_digest(current_hash, user["password_hash"]):
            return False, "Your current password is incorrect."

        new_salt = secrets.token_hex(16)
        new_hash = hash_password(new_password, new_salt)
        connection.execute(
            "UPDATE users SET password_salt = ?, password_hash = ? WHERE email = ?",
            (new_salt, new_hash, clean_email),
        )
    return True, ""


def reset_user_password(email: str, new_password: str):
    """Replace a password after the caller has verified a recovery code.

    This intentionally does not perform recovery-code validation itself: the
    application verifies the salted code stored in that student's private
    state before calling this small database operation.
    """
    clean_email = email.strip().lower()
    new_salt = secrets.token_hex(16)
    new_hash = hash_password(new_password, new_salt)

    if using_supabase():
        encoded_email = quote(clean_email, safe="")
        rows, error = _supabase_request(
            "GET",
            f"career_ai_users?email=eq.{encoded_email}&select=email&limit=1",
        )
        if error or not rows:
            return False, "No Career AI account was found for this email."
        _, error = _supabase_request(
            "PATCH",
            f"career_ai_users?email=eq.{encoded_email}",
            {"password_salt": new_salt, "password_hash": new_hash},
            {"Prefer": "return=minimal"},
        )
        return (not error), ("" if not error else "We could not reset your password right now.")

    with get_connection() as connection:
        result = connection.execute(
            "UPDATE users SET password_salt = ?, password_hash = ? WHERE email = ?",
            (new_salt, new_hash, clean_email),
        )
    if result.rowcount < 1:
        return False, "No Career AI account was found for this email."
    return True, ""


def save_student_state(email: str, state: dict):
    clean_email = email.strip().lower()
    if using_supabase():
        _, error = _supabase_request(
            "POST",
            "career_ai_states?on_conflict=email",
            {
                "email": clean_email,
                "state_json": state,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            {"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
        return not bool(error)

    safe_state = json.dumps(state, ensure_ascii=False, default=str)

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO student_states (email, state_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(email) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (clean_email, safe_state),
        )
    return True


def load_student_state(email: str) -> dict:
    clean_email = email.strip().lower()
    if using_supabase():
        rows, error = _supabase_request(
            "GET",
            f"career_ai_states?email=eq.{quote(clean_email, safe='')}&select=state_json&limit=1",
        )
        if error or not rows:
            return {}
        state = rows[0].get("state_json", {})
        if isinstance(state, dict):
            return state
        try:
            return json.loads(state)
        except (TypeError, json.JSONDecodeError):
            return {}

    with get_connection() as connection:
        row = connection.execute(
            "SELECT state_json FROM student_states WHERE email = ?",
            (clean_email,),
        ).fetchone()

    if not row:
        return {}

    try:
        return json.loads(row["state_json"])
    except json.JSONDecodeError:
        return {}


def list_users() -> list[dict[str, str]]:
    """Return non-sensitive account details for the protected admin page."""
    if using_supabase():
        rows, error = _supabase_request(
            "GET",
            "career_ai_users?select=student_id,name,email,created_at&order=created_at.desc",
        )
        return rows if not error and isinstance(rows, list) else []

    with get_connection() as connection:
        rows = connection.execute(
            "SELECT student_id, name, email, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def delete_user(email: str) -> bool:
    """Permanently delete a user and their saved quiz/profile data."""
    clean_email = email.strip().lower()
    if using_supabase():
        _, error = _supabase_request(
            "DELETE",
            f"career_ai_users?email=eq.{quote(clean_email, safe='')}",
            extra_headers={"Prefer": "return=representation"},
        )
        if error:
            return False
        # Some projects use a cascading foreign key and others do not. This
        # second request is harmless after a cascade and prevents orphaned
        # profile state when no cascade was configured.
        _, state_error = _supabase_request(
            "DELETE",
            f"career_ai_states?email=eq.{quote(clean_email, safe='')}",
            extra_headers={"Prefer": "return=minimal"},
        )
        return not bool(state_error)

    with get_connection() as connection:
        connection.execute("DELETE FROM student_states WHERE email = ?", (clean_email,))
        result = connection.execute("DELETE FROM users WHERE email = ?", (clean_email,))
    return result.rowcount > 0
