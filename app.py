from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    send_file
)

import os
import io
from datetime import datetime

import boto3
import psycopg2
from psycopg2 import IntegrityError
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from botocore.exceptions import ClientError, NoCredentialsError


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "cloud-dropper-secret-2026"
)

AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
AWS_BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# ============================================================
# FILE CONFIGURATION
# ============================================================

ALLOWED_EXTENSIONS = {
    "jpg",
    "jpeg",
    "png",
    "pdf",
    "mp4",
    "ppt",
    "pptx"
}

MAX_FILE_SIZE = 2 * 1024 * 1024


# ============================================================
# AWS S3
# ============================================================

def get_s3_client():
    """
    On EC2, boto3 uses the IAM role attached to the instance.
    No AWS access key is stored in the project.
    """

    return boto3.client(
        "s3",
        region_name=AWS_REGION
    )


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


# ============================================================
# DATABASE TABLES
# ============================================================

def create_tables():

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        # USERS TABLE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # FILES TABLE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                s3_key VARCHAR(500) NOT NULL,
                file_type VARCHAR(20) NOT NULL,
                file_size BIGINT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                CONSTRAINT fk_user
                FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
            );
        """)

        conn.commit()

        print("Database tables are ready.")

    except Exception as e:

        print("Database table error:", e)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# HELPERS
# ============================================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def get_file_icon(file_type):

    icons = {
        "jpg": "🖼️",
        "jpeg": "🌄",
        "png": "🟢",
        "pdf": "📄",
        "mp4": "🎬",
        "ppt": "📊",
        "pptx": "📈"
    }

    return icons.get(file_type.lower(), "📁")


def get_current_user():

    return session.get("user_id")


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:

            flash(
                "Please fill in all fields.",
                "danger"
            )

            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        conn = None
        cursor = None

        try:

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO users
                (name, email, password)
                VALUES (%s, %s, %s)
                """,
                (
                    name,
                    email,
                    hashed_password
                )
            )

            conn.commit()

            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(url_for("login"))

        except IntegrityError:

            if conn:
                conn.rollback()

            flash(
                "An account with this email already exists.",
                "danger"
            )

            return redirect(url_for("register"))

        except Exception as e:

            if conn:
                conn.rollback()

            print("Register error:", e)

            flash(
                "Registration failed. Please try again.",
                "danger"
            )

            return redirect(url_for("register"))

        finally:

            if cursor:
                cursor.close()

            if conn:
                conn.close()

    return render_template("register.html")


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:

        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        conn = None
        cursor = None

        try:

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, name, email, password
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

            if user:

                user_id = user[0]
                user_name = user[1]
                stored_password = user[3]

                if check_password_hash(
                    stored_password,
                    password
                ):

                    session["user_id"] = user_id
                    session["user_name"] = user_name

                    flash(
                        "Login successful.",
                        "success"
                    )

                    return redirect(
                        url_for("dashboard")
                    )

            flash(
                "Invalid email or password.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

        except Exception as e:

            print("Login error:", e)

            flash(
                "Unable to login right now.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

        finally:

            if cursor:
                cursor.close()

            if conn:
                conn.close()

    return render_template("login.html")


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("login"))


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect(url_for("login"))

    user_id = session["user_id"]
    user_name = session.get(
        "user_name",
        "User"
    )

    search = request.args.get(
        "search",
        ""
    ).strip()

    selected_type = request.args.get(
        "file_type",
        ""
    ).strip().lower()

    conn = None
    cursor = None

    files = []

    total_files = 0
    storage_used = 0

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT
                id,
                name,
                s3_key,
                file_type,
                file_size,
                uploaded_at
            FROM files
            WHERE user_id = %s
        """

        params = [user_id]

        # SEARCH
        if search:

            query += """
                AND LOWER(name)
                LIKE LOWER(%s)
            """

            params.append(
                f"%{search}%"
            )

        # FILTER
        if selected_type:

            query += """
                AND LOWER(file_type) = %s
            """

            params.append(
                selected_type
            )

        query += """
            ORDER BY uploaded_at DESC
        """

        cursor.execute(
            query,
            params
        )

        rows = cursor.fetchall()

        for row in rows:

            files.append({
                "id": row[0],
                "name": row[1],
                "s3_key": row[2],
                "type": row[3],
                "size": row[4],
                "uploaded_at": row[5].strftime(
                    "%d %b %Y, %I:%M %p"
                ),
                "icon": get_file_icon(row[3])
            })

        # TOTAL FILES
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM files
            WHERE user_id = %s
            """,
            (user_id,)
        )

        total_files = cursor.fetchone()[0]

        # TOTAL STORAGE
        cursor.execute(
            """
            SELECT COALESCE(
                SUM(file_size),
                0
            )
            FROM files
            WHERE user_id = %s
            """,
            (user_id,)
        )

        total_bytes = cursor.fetchone()[0]

        storage_used = round(
            total_bytes / 1024 / 1024,
            2
        )

    except Exception as e:

        print("Dashboard error:", e)

        flash(
            "Unable to load stored files.",
            "danger"
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

    return render_template(
        "index.html",
        user_name=user_name,
        files=files,
        total_files=total_files,
        storage_used=storage_used,
        search=search,
        selected_type=selected_type
    )


# ============================================================
# UPLOAD FILE
# ============================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload_file():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if "file" not in request.files:

        flash(
            "Please select a file.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    file = request.files["file"]

    if not file or file.filename == "":

        flash(
            "Please select a file.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    filename = file.filename

    if not allowed_file(filename):

        flash(
            "File type is not supported.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:

        flash(
            "File size must be less than 2 MB.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    extension = filename.rsplit(
        ".",
        1
    )[1].lower()

    user_id = session["user_id"]

    # Unique S3 key
    timestamp = datetime.now().strftime(
        "%Y%m%d%H%M%S%f"
    )

    s3_key = (
        f"user_{user_id}/"
        f"{timestamp}_{filename}"
    )

    conn = None
    cursor = None

    try:

        # Upload to S3
        s3 = get_s3_client()

        s3.upload_fileobj(
            file,
            AWS_BUCKET_NAME,
            s3_key
        )

        # Save metadata in PostgreSQL
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO files
            (
                user_id,
                name,
                s3_key,
                file_type,
                file_size
            )
            VALUES
            (%s, %s, %s, %s, %s)
            """,
            (
                user_id,
                filename,
                s3_key,
                extension,
                file_size
            )
        )

        conn.commit()

        flash(
            f"{filename} uploaded successfully.",
            "success"
        )

    except NoCredentialsError:

        if conn:
            conn.rollback()

        flash(
            "AWS credentials or IAM role are not available.",
            "danger"
        )

    except ClientError as e:

        if conn:
            conn.rollback()

        print("S3 error:", e)

        flash(
            "Unable to upload file to S3.",
            "danger"
        )

    except Exception as e:

        if conn:
            conn.rollback()

        print("Upload error:", e)

        flash(
            "Upload failed. Please try again.",
            "danger"
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

    return redirect(
        url_for("dashboard")
    )


# ============================================================
# DOWNLOAD FILE
# ============================================================

@app.route(
    "/download/<int:file_id>"
)
def download_file(file_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                name,
                s3_key
            FROM files
            WHERE id = %s
            AND user_id = %s
            """,
            (
                file_id,
                user_id
            )
        )

        result = cursor.fetchone()

        if not result:

            flash(
                "File not found.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        filename = result[0]
        s3_key = result[1]

        s3 = get_s3_client()

        response = s3.get_object(
            Bucket=AWS_BUCKET_NAME,
            Key=s3_key
        )

        file_data = response["Body"].read()

        return send_file(
            io.BytesIO(file_data),
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:

        print("Download error:", e)

        flash(
            "Unable to download the file.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()


# ============================================================
# DELETE FILE
# ============================================================

@app.route(
    "/delete/<int:file_id>",
    methods=["POST"]
)
def delete_file(file_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    user_id = session["user_id"]

    conn = None
    cursor = None

    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                name,
                s3_key
            FROM files
            WHERE id = %s
            AND user_id = %s
            """,
            (
                file_id,
                user_id
            )
        )

        result = cursor.fetchone()

        if not result:

            flash(
                "File not found.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        filename = result[0]
        s3_key = result[1]

        # Delete from S3
        s3 = get_s3_client()

        s3.delete_object(
            Bucket=AWS_BUCKET_NAME,
            Key=s3_key
        )

        # Delete database record
        cursor.execute(
            """
            DELETE FROM files
            WHERE id = %s
            AND user_id = %s
            """,
            (
                file_id,
                user_id
            )
        )

        conn.commit()

        flash(
            f"{filename} deleted successfully.",
            "success"
        )

    except Exception as e:

        if conn:
            conn.rollback()

        print("Delete error:", e)

        flash(
            "Unable to delete the file.",
            "danger"
        )

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

    return redirect(
        url_for("dashboard")
    )


# ============================================================
# DASHBOARD PREVIEW
# ============================================================

@app.route("/preview")
def dashboard_preview():

    demo_files = [
        {
            "id": 1,
            "name": "Cloud_Project.pdf",
            "type": "pdf",
            "size": 850000,
            "uploaded_at": "25 Oct 2026",
            "icon": "📄"
        },
        {
            "id": 2,
            "name": "Presentation.pptx",
            "type": "pptx",
            "size": 1250000,
            "uploaded_at": "24 Oct 2026",
            "icon": "📊"
        },
        {
            "id": 3,
            "name": "Project_Image.png",
            "type": "png",
            "size": 640000,
            "uploaded_at": "23 Oct 2026",
            "icon": "🖼️"
        }
    ]

    return render_template(
        "index.html",
        user_name="Srushti",
        files=demo_files,
        total_files=3,
        storage_used=2.61,
        search="",
        selected_type=""
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    # Do not initialize RDS when testing locally
    # because your RDS is private.

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )