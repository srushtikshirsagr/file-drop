from flask import (
    Flask,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    session,
    send_file
)

from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from io import BytesIO
from dotenv import load_dotenv
from botocore.exceptions import BotoCoreError, ClientError

import boto3
import psycopg2
import os
import uuid


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "change-this-secret-key"
)


# ============================================================
# AWS CONFIGURATION
# ============================================================

AWS_REGION = os.getenv(
    "AWS_REGION",
    "ap-south-1"
)

AWS_BUCKET_NAME = os.getenv(
    "AWS_BUCKET_NAME"
)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


# ============================================================
# FILE SETTINGS
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

# Maximum file size = 2 MB
MAX_FILE_SIZE = 2 * 1024 * 1024


FILE_ICONS = {
    "jpg": "🖼️",
    "jpeg": "🖼️",
    "png": "🖼️",
    "pdf": "📄",
    "mp4": "🎬",
    "ppt": "📊",
    "pptx": "📊"
}


# ============================================================
# AWS S3 CONNECTION
# ============================================================

def get_s3_client():
    """
    Creates an S3 client.

    On EC2, boto3 automatically uses the IAM Role
    attached to the EC2 instance.

    Therefore, AWS access keys are not stored
    inside the application code.
    """

    return boto3.client(
        "s3",
        region_name=AWS_REGION
    )


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db_connection():
    """
    Connects Flask to PostgreSQL RDS.
    """

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


# ============================================================
# CREATE DATABASE TABLES
# ============================================================

def create_tables():

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        # -------------------------
        # USERS TABLE
        # -------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # -------------------------
        # FILES TABLE
        # -------------------------

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id)
                    ON DELETE CASCADE,
                filename VARCHAR(255) NOT NULL,
                s3_key VARCHAR(500) NOT NULL,
                file_type VARCHAR(50),
                file_size BIGINT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()

        print("Database tables are ready.")

    except Exception as error:

        print("Database setup error:", error)

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# LOGIN REQUIRED DECORATOR
# ============================================================

def login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login first.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

        return function(*args, **kwargs)

    return decorated_function


# ============================================================
# CHECK FILE TYPE
# ============================================================

def allowed_file(filename):

    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# ============================================================
# GET USER FILES
# ============================================================

def get_user_files(
    user_id,
    search="",
    file_type=""
):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            SELECT
                id,
                filename,
                s3_key,
                file_type,
                file_size,
                uploaded_at
            FROM files
            WHERE user_id = %s
        """

        values = [user_id]

        # -------------------------
        # SEARCH
        # -------------------------

        if search:

            query += """
                AND filename ILIKE %s
            """

            values.append(
                "%" + search + "%"
            )

        # -------------------------
        # FILE TYPE FILTER
        # -------------------------

        if file_type:

            query += """
                AND file_type = %s
            """

            values.append(file_type)

        query += """
            ORDER BY uploaded_at DESC
        """

        cursor.execute(
            query,
            tuple(values)
        )

        rows = cursor.fetchall()

        files = []

        for row in rows:

            files.append({
                "id": row[0],
                "name": row[1],
                "s3_key": row[2],
                "type": row[3],
                "size": row[4],
                "uploaded_at": row[5],
                "icon": FILE_ICONS.get(
                    row[3],
                    "📁"
                )
            })

        return files

    except Exception as error:

        print(
            "Error getting files:",
            error
        )

        return []

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not name or not email or not password:

            flash(
                "Please fill all fields.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            # Check if email already exists

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:

                flash(
                    "Email already registered. Please login.",
                    "warning"
                )

                return redirect(
                    url_for("login")
                )

            # Hash password

            password_hash = generate_password_hash(
                password
            )

            # Insert user

            cursor.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password_hash
                )
                VALUES (%s, %s, %s)
                """,
                (
                    name,
                    email,
                    password_hash
                )
            )

            connection.commit()

            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(
                url_for("login")
            )

        except Exception as error:

            if connection:
                connection.rollback()

            print(
                "Registration error:",
                error
            )

            flash(
                "Registration failed. Please try again.",
                "danger"
            )

            return redirect(
                url_for("register")
            )

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template(
        "register.html"
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:

            flash(
                "Please enter email and password.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    name,
                    email,
                    password_hash
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

            if user and check_password_hash(
                user[3],
                password
            ):

                session["user_id"] = user[0]
                session["user_name"] = user[1]
                session["user_email"] = user[2]

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

        except Exception as error:

            print(
                "Login error:",
                error
            )

            flash(
                "Unable to login. Please try again.",
                "danger"
            )

            return redirect(
                url_for("login")
            )

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template(
        "login.html"
    )


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

    return redirect(
        url_for("login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():

    search = request.args.get(
        "search",
        ""
    ).strip()

    file_type = request.args.get(
        "file_type",
        ""
    ).strip().lower()

    files = get_user_files(
        session["user_id"],
        search,
        file_type
    )

    total_files = len(files)

    storage_used = sum(
        file["size"] or 0
        for file in files
    )

    # Convert bytes to MB

    storage_used_mb = round(
        storage_used / (1024 * 1024),
        2
    )

    return render_template(
        "index.html",
        user_name=session.get(
            "user_name",
            "User"
        ),
        files=files,
        total_files=total_files,
        storage_used=storage_used_mb,
        search=search,
        selected_type=file_type
    )


# ============================================================
# UPLOAD FILE
# ============================================================

@app.route(
    "/upload",
    methods=["POST"]
)
@login_required
def upload_file():

    if "file" not in request.files:

        flash(
            "Please select a file.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    file = request.files["file"]

    if file.filename == "":

        flash(
            "No file selected.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    filename = secure_filename(
        file.filename
    )

    if not filename:

        flash(
            "Invalid filename.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    # Check extension

    if not allowed_file(filename):

        flash(
            "File type is not supported.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    # Read file

    file_data = file.read()

    file_size = len(file_data)

    # Check size

    if file_size > MAX_FILE_SIZE:

        flash(
            "File size must be less than 2 MB.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    # Get extension

    file_type = filename.rsplit(
        ".",
        1
    )[1].lower()

    # Generate unique S3 key

    unique_name = (
        str(uuid.uuid4())
        + "_"
        + filename
    )

    s3_key = (
        "users/"
        + str(session["user_id"])
        + "/"
        + unique_name
    )

    try:

        # -------------------------
        # Upload to S3
        # -------------------------

        s3 = get_s3_client()

        s3.upload_fileobj(
            BytesIO(file_data),
            AWS_BUCKET_NAME,
            s3_key
        )

        # -------------------------
        # Save metadata in RDS
        # -------------------------

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO files
            (
                user_id,
                filename,
                s3_key,
                file_type,
                file_size
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                session["user_id"],
                filename,
                s3_key,
                file_type,
                file_size
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        flash(
            "File uploaded successfully.",
            "success"
        )

    except (BotoCoreError, ClientError) as error:

        print(
            "S3 upload error:",
            error
        )

        flash(
            "File upload to cloud storage failed.",
            "danger"
        )

    except Exception as error:

        print(
            "Upload error:",
            error
        )

        flash(
            "File upload failed.",
            "danger"
        )

    return redirect(
        url_for("dashboard")
    )


# ============================================================
# DOWNLOAD FILE
# ============================================================

@app.route(
    "/download/<int:file_id>"
)
@login_required
def download_file(file_id):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                filename,
                s3_key
            FROM files
            WHERE id = %s
            AND user_id = %s
            """,
            (
                file_id,
                session["user_id"]
            )
        )

        file_record = cursor.fetchone()

        if not file_record:

            flash(
                "File not found.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        filename = file_record[0]
        s3_key = file_record[1]

        # Get object from S3

        s3 = get_s3_client()

        response = s3.get_object(
            Bucket=AWS_BUCKET_NAME,
            Key=s3_key
        )

        file_data = response["Body"].read()

        return send_file(
            BytesIO(file_data),
            as_attachment=True,
            download_name=filename
        )

    except Exception as error:

        print(
            "Download error:",
            error
        )

        flash(
            "Unable to download file.",
            "danger"
        )

        return redirect(
            url_for("dashboard")
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ============================================================
# DELETE FILE
# ============================================================

@app.route(
    "/delete/<int:file_id>",
    methods=["POST"]
)
@login_required
def delete_file(file_id):

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        # Get file information

        cursor.execute(
            """
            SELECT
                filename,
                s3_key
            FROM files
            WHERE id = %s
            AND user_id = %s
            """,
            (
                file_id,
                session["user_id"]
            )
        )

        file_record = cursor.fetchone()

        if not file_record:

            flash(
                "File not found.",
                "danger"
            )

            return redirect(
                url_for("dashboard")
            )

        filename = file_record[0]
        s3_key = file_record[1]

        # Delete from S3

        s3 = get_s3_client()

        s3.delete_object(
            Bucket=AWS_BUCKET_NAME,
            Key=s3_key
        )

        # Delete metadata from database

        cursor.execute(
            """
            DELETE FROM files
            WHERE id = %s
            AND user_id = %s
            """,
            (
                file_id,
                session["user_id"]
            )
        )

        connection.commit()

        flash(
            f"{filename} deleted successfully.",
            "success"
        )

    except Exception as error:

        if connection:
            connection.rollback()

        print(
            "Delete error:",
            error
        )

        flash(
            "Unable to delete file.",
            "danger"
        )

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(
        url_for("dashboard")
    )


# ============================================================
# DASHBOARD UI PREVIEW
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
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    create_tables()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )