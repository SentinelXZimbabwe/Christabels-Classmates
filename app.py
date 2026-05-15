from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
import os
from datetime import datetime
import uuid
from io import BytesIO
import functions

app = Flask(__name__)
app.secret_key = "super_secret_key_change_me"

# -------------------------
# DATABASE
# -------------------------
DB_FOLDER = "database"
DB_PATH = os.path.join(DB_FOLDER, "app.db")
os.makedirs(DB_FOLDER, exist_ok=True)

# -------------------------
# INIT DB
# -------------------------
def init_db():

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            media_type TEXT,
            filename TEXT,
            file_blob BLOB
        )
    """)

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

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            media_id INTEGER,
            UNIQUE(user_id, media_id)
        )
    """)

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
# INIT EXTRA TABLES
# -------------------------
functions.init_reset_table()

# -------------------------
# ADMIN CREDENTIALS
# -------------------------
ADMIN_USERNAME = "Christabel Lalaz"
ADMIN_PASSWORD = "christabel12234@"

# ======================================================
# MEDIA TYPE DETECTION
# ======================================================
def get_media_category(filename):

    ext = filename.lower().split(".")[-1]

    if ext in ["mp4", "mov", "avi", "mkv", "webm"]:
        return "video"

    elif ext in ["mp3", "wav", "aac", "ogg"]:
        return "audio"

    elif ext in ["jpg", "jpeg", "png", "webp"]:
        return "image"

    return "unknown"

# ======================================================
# USERNAME RESOLVER
# ======================================================
def get_username(user_id):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT username FROM users WHERE id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    conn.close()

    return row[0] if row else "Unknown User"

# ======================================================
# LANDING PAGE
# ======================================================
@app.route("/")
def landing():
    return render_template("landing.html")

# ======================================================
# MAIN FEED
# ======================================================
@app.route("/app")
def app_feed():

    if not session.get("user_id"):
        return redirect("/login")

    search = request.args.get("search", "").strip().lower()
    media_type = request.args.get("type")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = "SELECT id, title, media_type, filename FROM media"
    params = []

    if media_type in ["video", "audio", "image"]:
        query += " WHERE media_type=?"
        params.append(media_type)

    cursor.execute(query, params)

    rows = cursor.fetchall()

    media = []

    for r in rows:

        if search and search not in r[1].lower():
            continue

        media.append({
            "id": r[0],
            "title": r[1],
            "type": r[2],
            "filename": r[3]
        })

    # -------------------------
    # LIKES
    # -------------------------
    cursor.execute("""
        SELECT media_id, COUNT(*)
        FROM likes
        GROUP BY media_id
    """)

    likes = dict(cursor.fetchall())

    # -------------------------
    # COMMENTS
    # -------------------------
    cursor.execute("""
        SELECT
            id,
            media_id,
            comment,
            created_at,
            user_id
        FROM comments
        ORDER BY created_at DESC
    """)

    raw_comments = cursor.fetchall()

    conn.close()

    comments = {}

    for comment_id, m_id, comment, created_at, user_id in raw_comments:

        comments.setdefault(m_id, []).append({

            "id": comment_id,
            "comment": comment,
            "time": created_at,
            "user": get_username(user_id),
            "user_id": user_id

        })

    return render_template(

        "app.html",

        media=media,
        likes=likes,
        comments=comments,

        logged_in=True,

        search=search,
        active_type=media_type,

        no_results=len(media) == 0

    )

# ======================================================
# MEDIA STREAM
# ======================================================
@app.route("/media/<int:media_id>")
def media(media_id):

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT filename, file_blob FROM media WHERE id=?",
        (media_id,)
    )

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

        cursor.execute(
            "INSERT INTO likes (user_id, media_id) VALUES (?, ?)",
            (session["user_id"], media_id)
        )

        conn.commit()

    except:
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

    comment_text = request.form["comment"].strip()

    if not comment_text:
        return redirect("/app")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO comments (
            user_id,
            media_id,
            comment,
            created_at
        )
        VALUES (?, ?, ?, ?)
    """, (

        session["user_id"],
        media_id,
        comment_text,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ))

    conn.commit()
    conn.close()

    return redirect("/app")

# ======================================================
# DELETE COMMENT
# ======================================================
@app.route("/delete-comment/<int:comment_id>")
def delete_comment(comment_id):

    if not session.get("user_id"):
        return redirect("/login")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id
        FROM comments
        WHERE id=?
    """, (comment_id,))

    row = cursor.fetchone()

    if not row:

        conn.close()
        return redirect("/app")

    comment_owner = row[0]

    # USER CAN DELETE OWN COMMENT
    # ADMIN CAN DELETE ANY COMMENT
    if (
        comment_owner == session["user_id"] or
        session.get("admin")
    ):

        cursor.execute("""
            DELETE FROM comments
            WHERE id=?
        """, (comment_id,))

        conn.commit()

    conn.close()

    return redirect("/app")

# ======================================================
# DELETE MEDIA (ADMIN)
# ======================================================
@app.route("/delete-media/<int:media_id>")
def delete_media(media_id):

    if not session.get("admin"):
        return redirect("/admin")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # DELETE LIKES
    cursor.execute("""
        DELETE FROM likes
        WHERE media_id=?
    """, (media_id,))

    # DELETE COMMENTS
    cursor.execute("""
        DELETE FROM comments
        WHERE media_id=?
    """, (media_id,))

    # DELETE MEDIA
    cursor.execute("""
        DELETE FROM media
        WHERE id=?
    """, (media_id,))

    conn.commit()
    conn.close()

    return redirect("/admin")

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
                INSERT INTO users (
                    id,
                    full_name,
                    username,
                    email,
                    password,
                    created_at
                )
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

        except:
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
            SELECT id, username
            FROM users
            WHERE username=? AND password=?
        """, (

            request.form["username"],
            request.form["password"]

        ))

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
# FORGOT PASSWORD
# ======================================================
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"]

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE email=?",
            (email,)
        )

        user = cursor.fetchone()

        conn.close()

        if not user:
            return "Email not found", 404

        token = functions.create_reset_token(user[0])

        base_url = request.host_url.rstrip("/")

        functions.send_reset_email(
            email,
            token,
            base_url
        )

        return "Reset link sent to email"

    return render_template("forgot-password.html")

# ======================================================
# RESET PASSWORD
# ======================================================
@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    user_id = functions.verify_token(token)

    if not user_id:
        return "Invalid or expired token", 400

    if request.method == "POST":

        new_password = request.form["password"]

        functions.update_password(
            user_id,
            new_password
        )

        return redirect("/login")

    return render_template(
        "reset-password.html",
        token=token
    )

# ======================================================
# API REQUEST PAGE
# ======================================================
@app.route("/request-api", methods=["GET", "POST"])
def request_api():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        tier = request.form["tier"]
        use_case = request.form["use_case"]

        base_url = request.host_url.rstrip("/")

        functions.send_api_request_email(
            name,
            email,
            tier,
            use_case,
            base_url
        )

        return render_template(
            "api-request-success.html"
        )

    return render_template("request-api.html")

# ======================================================
# ADMIN PANEL
# ======================================================
@app.route("/admin", methods=["GET", "POST"])
def admin():

    # LOGIN HANDLING
    if request.method == "POST":

        if (
            request.form["username"] == ADMIN_USERNAME and
            request.form["password"] == ADMIN_PASSWORD
        ):

            session["admin"] = True

            return redirect("/admin")

    if not session.get("admin"):
        return render_template("admin.html")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # -------------------------
    # MEDIA
    # -------------------------
    cursor.execute("""
        SELECT id, title, media_type, filename
        FROM media
    """)

    media = cursor.fetchall()

    # -------------------------
    # USERS
    # -------------------------
    cursor.execute("""
        SELECT
            id,
            full_name,
            username,
            email,
            created_at
        FROM users
        ORDER BY created_at DESC
    """)

    users = cursor.fetchall()

    # -------------------------
    # KPI METRICS
    # -------------------------
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM media")
    total_media = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM likes")
    total_likes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM comments")
    total_comments = cursor.fetchone()[0]

    conn.close()

    return render_template(

        "admin.html",

        media=media,
        users=users,

        total_users=total_users,
        total_media=total_media,
        total_likes=total_likes,
        total_comments=total_comments

    )

# ======================================================
# UPLOAD
# ======================================================
@app.route("/upload", methods=["POST"])
def upload():

    if not session.get("admin"):
        return redirect("/admin")

    file = request.files["file"]

    filename = file.filename
    blob = file.read()

    media_type = get_media_category(filename)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO media (
            title,
            media_type,
            filename,
            file_blob
        )
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
# RUN
# ======================================================
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )