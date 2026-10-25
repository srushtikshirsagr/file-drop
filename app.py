import os
from functools import wraps
from io import BytesIO

import boto3
import psycopg2
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from flask import (
    Flask, flash, redirect, render_template, request,
    send_file, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret-key")

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME", "clouddrop26")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "clouddropper")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf", "mp4", "ppt", "pptx"}
MAX_FILE_SIZE = 2 * 1024 * 1024


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        connect_timeout=10,
    )


def get_s3_client():
    # On EC2 this uses the attached IAM role.
    # Locally it can use AWS credentials configured in the environment.
    return boto3.client("s3", region_name=AWS_REGION)


def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    original_name VARCHAR(255) NOT NULL,
                    s3_key TEXT UNIQUE NOT NULL,
                    file_type VARCHAR(20) NOT NULL,
                    file_size BIGINT NOT NULL,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        conn.commit()
    finally:
        conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def file_icon(file_type):
    icons = {
        "jpg": "🖼️",
        "jpeg": "🖼️",
        "png": "🟢",
        "pdf": "📄",
        "mp4": "🎬",
        "ppt": "📊",
        "pptx": "📈",
    }
    return icons.get(file_type.lower(), "📁")


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if len(password) < 6:
            flash("Password must contain at least 6 characters.", "danger")
            return render_template("register.html")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email = %s", (email,))
                if cur.fetchone():
                    flash("An account with this email already exists.", "danger")
                    return render_template("register.html")

                cur.execute(
                    """
                    INSERT INTO users (name, email, password_hash)
                    VALUES (%s, %s, %s)
                    """,
                    (name, email, generate_password_hash(password)),
                )
            conn.commit()
        finally:
            conn.close()

        flash("Account created successfully. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, name, password_hash, role FROM users WHERE email = %s",
                    (email,),
                )
                user = cur.fetchone()
        finally:
            conn.close()

        if not user or not check_password_hash(user[2], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user[0]
        session["user_name"] = user[1]
        session["role"] = user[3]

        # Send admin to Admin Dashboard
        if user[3] == "admin":
            return redirect(url_for("admin_dashboard"))

        # Normal users continue to existing dashboard
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            # Total users
            cur.execute("SELECT COUNT(*) FROM users")
            total_users = cur.fetchone()[0]

            # Total files
            cur.execute("SELECT COUNT(*) FROM files")
            total_files = cur.fetchone()[0]

            # Total storage
            cur.execute("SELECT COALESCE(SUM(file_size), 0) FROM files")
            total_storage = cur.fetchone()[0]

            # Registered users
            cur.execute("""
                SELECT id, name, email, role, created_at
                FROM users
                ORDER BY created_at DESC
            """)
            users = cur.fetchall()

            # All uploaded files
            cur.execute("""
                SELECT files.id, files.original_name, files.file_type,
                       files.file_size, files.uploaded_at, users.name
                FROM files
                JOIN users ON files.user_id = users.id
                ORDER BY files.uploaded_at DESC
            """)
            files = cur.fetchall()

    finally:
        conn.close()

    return render_template(
        "admin.html",
        total_users=total_users,
        total_files=total_files,
        total_storage=total_storage,
        users=users,
        files=files,
    )

@app.route("/admin/delete-file/<int:file_id>", methods=["POST"])
def admin_delete_file(file_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()

    try:
        with conn.cursor() as cur:
            # Get the S3 key before deleting the database record
            cur.execute(
                "SELECT s3_key FROM files WHERE id = %s",
                (file_id,)
            )
            file_record = cur.fetchone()

            if not file_record:
                flash("File not found.", "danger")
                return redirect(url_for("admin_dashboard"))

            s3_key = file_record[0]

            # Delete file from S3
            s3 = get_s3_client()
            s3.delete_object(
                Bucket=os.getenv("AWS_BUCKET_NAME"),
                Key=s3_key
            )

            # Delete file from database
            cur.execute(
                "DELETE FROM files WHERE id = %s",
                (file_id,)
            )

        conn.commit()
        flash("File deleted successfully.", "success")

    except Exception as e:
        conn.rollback()
        flash("Unable to delete file.", "danger")
        print("Admin delete file error:", e)

    finally:
        conn.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/dashboard")
@login_required
def dashboard():
    search = request.args.get("search", "").strip()
    selected_type = request.args.get("file_type", "").strip().lower()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT id, original_name, file_type, file_size, uploaded_at
                FROM files
                WHERE user_id = %s
            """
            params = [session["user_id"]]

            if search:
                query += " AND original_name ILIKE %s"
                params.append(f"%{search}%")

            if selected_type in ALLOWED_EXTENSIONS:
                query += " AND file_type = %s"
                params.append(selected_type)

            query += " ORDER BY uploaded_at DESC"

            cur.execute(query, tuple(params))
            rows = cur.fetchall()

            cur.execute(
                "SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM files WHERE user_id = %s",
                (session["user_id"],),
            )
            total_files, total_bytes = cur.fetchone()
    finally:
        conn.close()

    file_list = []
    for row in rows:
        file_list.append({
            "id": row[0],
            "name": row[1],
            "type": row[2],
            "size": row[3],
            "uploaded_at": row[4].strftime("%d %b %Y, %I:%M %p"),
            "icon": file_icon(row[2]),
        })

    storage_used = round(total_bytes / (1024 * 1024), 2)

    return render_template(
        "index.html",
        user_name=session.get("user_name", "User"),
        files=file_list,
        total_files=total_files,
        storage_used=storage_used,
        search=search,
        selected_type=selected_type,
    )


@app.route("/upload", methods=["POST"])
@login_required
def upload_file():
    uploaded = request.files.get("file")

    if not uploaded or not uploaded.filename:
        flash("Please select a file.", "danger")
        return redirect(url_for("dashboard"))

    filename = uploaded.filename.strip()

    if not allowed_file(filename):
        flash("Unsupported file type.", "danger")
        return redirect(url_for("dashboard"))

    uploaded.seek(0, os.SEEK_END)
    size = uploaded.tell()
    uploaded.seek(0)

    if size > MAX_FILE_SIZE:
        flash("File size must be 2 MB or less.", "danger")
        return redirect(url_for("dashboard"))

    extension = filename.rsplit(".", 1)[1].lower()
    safe_name = os.path.basename(filename)
    s3_key = f"users/{session['user_id']}/{safe_name}"

    try:
        s3 = get_s3_client()
        s3.upload_fileobj(
            uploaded,
            AWS_BUCKET_NAME,
            s3_key,
            ExtraArgs={"ContentType": uploaded.content_type or "application/octet-stream"},
        )
    except (ClientError, NoCredentialsError) as exc:
        app.logger.exception("S3 upload failed")
        flash("Cloud upload failed. Check S3 bucket/IAM configuration.", "danger")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO files
                    (user_id, original_name, s3_key, file_type, file_size)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session["user_id"], safe_name, s3_key, extension, size),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        try:
            get_s3_client().delete_object(Bucket=AWS_BUCKET_NAME, Key=s3_key)
        except Exception:
            app.logger.exception("Rollback S3 delete failed")
        flash("File database entry failed, so the upload was cancelled.", "danger")
        return redirect(url_for("dashboard"))
    finally:
        conn.close()

    flash("File uploaded successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/download/<int:file_id>")
@login_required
def download_file(file_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT original_name, s3_key
                FROM files
                WHERE id = %s AND user_id = %s
                """,
                (file_id, session["user_id"]),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        flash("File not found.", "danger")
        return redirect(url_for("dashboard"))

    try:
        response = get_s3_client().get_object(
            Bucket=AWS_BUCKET_NAME,
            Key=row[1],
        )
        data = response["Body"].read()
        return send_file(
            BytesIO(data),
            as_attachment=True,
            download_name=row[0],
            mimetype=response.get("ContentType") or "application/octet-stream",
        )
    except ClientError:
        flash("Could not download the file from cloud storage.", "danger")
        return redirect(url_for("dashboard"))


@app.route("/delete/<int:file_id>", methods=["POST"])
@login_required
def delete_file(file_id):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s3_key
                FROM files
                WHERE id = %s AND user_id = %s
                """,
                (file_id, session["user_id"]),
            )
            row = cur.fetchone()

            if not row:
                flash("File not found.", "danger")
                return redirect(url_for("dashboard"))

            get_s3_client().delete_object(
                Bucket=AWS_BUCKET_NAME,
                Key=row[0],
            )

            cur.execute(
                "DELETE FROM files WHERE id = %s AND user_id = %s",
                (file_id, session["user_id"]),
            )

        conn.commit()
    except Exception:
        conn.rollback()
        app.logger.exception("Delete failed")
        flash("Could not delete the file.", "danger")
        return redirect(url_for("dashboard"))
    finally:
        conn.close()

    flash("File deleted successfully.", "success")
    return redirect(url_for("dashboard"))


@app.context_processor
def inject_globals():
    return {
        "supported_types": ["jpg", "jpeg", "png", "pdf", "mp4", "ppt", "pptx"]
    }


if __name__ == "__main__":
    try:
        init_db()
        print("Database tables are ready.")
    except Exception as exc:
        print("Database initialization failed:", exc)

    app.run(host="0.0.0.0", port=5000, debug=True)
