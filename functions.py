import sqlite3
import smtplib
import ssl
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText

# -------------------------
# SMTP CONFIG
# -------------------------
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_SENDER = "christabelsclassmates@gmail.com"
EMAIL_PASSWORD = "oqjg qozb srvy xaud"  # Gmail App Password

# -------------------------
# DATABASE
# -------------------------
DB_PATH = "database/app.db"


# ======================================================
# INIT TABLES
# ======================================================

def init_reset_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            token TEXT UNIQUE,
            expiry TEXT
        )
    """)

    conn.commit()
    conn.close()


# ======================================================
# TOKEN GENERATION
# ======================================================

def generate_token():
    return str(uuid.uuid4())


# ======================================================
# PASSWORD RESET SYSTEM
# ======================================================

def create_reset_token(user_id):
    token = generate_token()
    expiry = (datetime.now() + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO password_resets (user_id, token, expiry)
        VALUES (?, ?, ?)
    """, (user_id, token, expiry))

    conn.commit()
    conn.close()

    return token


def send_reset_email(to_email, token, base_url):
    reset_link = f"{base_url}/reset-password/{token}"

    subject = "Password Reset Request"

    body = f"""
You requested a password reset.

----------------------------------------
Reset Link:
{reset_link}
----------------------------------------

This link expires in 30 minutes.

If you did not request this, ignore this email.
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email

    context = ssl.create_default_context()

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())


def verify_token(token):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, expiry FROM password_resets WHERE token=?
    """, (token,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    expiry = datetime.strptime(row[1], "%Y-%m-%d %H:%M:%S")

    if datetime.now() > expiry:
        return None

    return row[0]


def update_password(user_id, new_password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE users SET password=? WHERE id=?
    """, (new_password, user_id))

    conn.commit()
    conn.close()


# ======================================================
# API REQUEST SYSTEM (EMAIL-BASED)
# ======================================================

def send_api_request_email(name, email, tier, use_case, base_url):
    subject = f"API Key Request - {tier}"

    body = f"""
New API Key Request Submitted

----------------------------------------
Name: {name}
Email: {email}
Tier Requested: {tier}

Use Case:
{use_case}
----------------------------------------

Platform Origin:
{base_url}

Next Step:
Review request and issue API key manually if approved.
"""

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_SENDER  # sent to your inbox

    context = ssl.create_default_context()

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_SENDER, msg.as_string())
