from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
import os
from datetime import datetime
import uuid
from io import BytesIO

app = Flask(__name__)
app.secret_key = "super_secret_key_change_me"

# -------------------------
# DATABASE PATH
# -------------------------
DB_FOLDER = "database"
DB_PATH = os.path.join(DB_FOLDER, "app.db")
os.makedirs(DB_FOLDER, exist_ok=True)

# -------------------------
# INIT DATABASE
# -------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # MEDIA TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            media_type TEXT,
            filename TEXT,
            file_blob BLOB
        )
    """)

    # USERS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            full_name TEXT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT,
            created_at TEXT
        )
    """)

    # LIKES TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            media_id INTEGER,
            UNIQUE(user_id, media_id)
        )
    """)

    # COMMENTS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            media_id INTEGER,
            comment TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# -------------------------
# ADMIN CREDENTIALS
# -------------------------
ADMIN_USERNAME = "Christabel Lalaz"
ADMIN_PASSWORD = "christabel12234@"

# ======================================================
# LANDING PAGE (ENTRY POINT)
# ======================================================
@app.route("/")
def landing():
    return render_template("landing.html")


# ======================================================
# USER APP FEED
# ======================================================
@app.route("/app")
def app_feed():
    if not session.get("user_id"):
        return redirect("/login")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, media_type, filename FROM media")
    media = cursor.fetchall()

    cursor.execute("SELECT media_id, COUNT(*) FROM likes GROUP BY media_id")
    likes = dict(cursor.fetchall())

    cursor.execute("""
        SELECT media_id, comment, created_at, user_id
        FROM comments
        ORDER BY created_at DESC
    """)
    raw_comments = cursor.fetchall()

    conn.close()

    comments = {}
    for m_id, comment, created_at, user_id in raw_comments:
        comments.setdefault(m_id, []).append({
            "comment": comment,
            "time": created_at,
            "user": user_id
        })

    return render_template(
        "app.html",
        media=media,
        likes=likes,
        comments=comments,
        logged_in=True
    )


# ======================================================
# MEDIA STREAMING
# ======================================================
@app.route("/media/<int:media_id>")
def media(media_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT filename, file_blob FROM media WHERE id=?", (media_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return send_file(
            BytesIO(row[1]),
            download_name=row[0],
            as_attachment=False
        )

    return "Not found", 404


# ======================================================
# LIKE SYSTEM
# ======================================================
@app.route("/like/<int:media_id>")
def like(media_id):
    if not session.get("user_id"):
        return "Login required", 403

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO likes (user_id, media_id)
            VALUES (?, ?)
        """, (session["user_id"], media_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass

    conn.close()
    return redirect("/app")


# ======================================================
# COMMENT SYSTEM
# ======================================================
@app.route("/comment/<int:media_id>", methods=["POST"])
def comment(media_id):
    if not session.get("user_id"):
        return "Login required", 403

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO comments (user_id, media_id, comment, created_at)
        VALUES (?, ?, ?, ?)
    """, (
        session["user_id"],
        media_id,
        request.form["comment"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()

    return redirect("/app")


# ======================================================
# CREATE ACCOUNT
# ======================================================
@app.route("/create-account", methods=["GET", "POST"])
def create_account():
    if request.method == "POST":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (id, full_name, username, email, password, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                request.form["full_name"],
                request.form["username"],
                request.form["email"],
                request.form["password"],
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            conn.commit()
        except sqlite3.IntegrityError:
            return "User already exists", 400
        finally:
            conn.close()

        return redirect("/login")

    return render_template("create-account.html")


# ======================================================
# LOGIN
# ======================================================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, username FROM users
            WHERE username=? AND password=?
        """, (request.form["username"], request.form["password"]))

        user = cursor.fetchone()
        conn.close()

        if user:
            session["user_id"] = user[0]
            session["username"] = user[1]
            return redirect("/app")

        return "Invalid credentials", 401

    return render_template("login.html")


# ======================================================
# LOGOUT
# ======================================================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ======================================================
# ADMIN PANEL
# ======================================================
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form["username"] == ADMIN_USERNAME and request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin")

    if not session.get("admin"):
        return render_template("admin.html")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, media_type, filename FROM media")
    media = cursor.fetchall()

    conn.close()

    return render_template("admin.html", media=media)


# ======================================================
# MEDIA UPLOAD (ADMIN ONLY)
# ======================================================
@app.route("/upload", methods=["POST"])
def upload():
    if not session.get("admin"):
        return redirect("/admin")

    file = request.files["file"]
    filename = file.filename
    blob = file.read()

    media_type = "video" if filename.split(".")[-1] in ["mp4", "mov", "avi"] else "audio"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO media (title, media_type, filename, file_blob)
        VALUES (?, ?, ?, ?)
    """, (
        request.form["title"],
        media_type,
        filename,
        blob
    ))

    conn.commit()
    conn.close()

    return redirect("/admin")


# ======================================================
# RUN APP
# ======================================================
if __name__ == "__main__":
    app.run(debug=True)
