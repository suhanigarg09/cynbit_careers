
import os
import re
import sqlite3
import secrets
from datetime import datetime
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, abort
)
from werkzeug.utils import secure_filename

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-key")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(INSTANCE_DIR, exist_ok=True)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE = os.path.join(INSTANCE_DIR, "careers.db")

ALLOWED_EXTENSIONS = {"pdf"}
MAX_FILE_SIZE = 5 * 1024 * 1024

app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            department TEXT NOT NULL,
            location TEXT NOT NULL,
            job_type TEXT NOT NULL,
            description TEXT NOT NULL,
            requirements TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_code TEXT UNIQUE NOT NULL,
            job_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            skills TEXT NOT NULL,
            introduction TEXT NOT NULL,
            resume TEXT NOT NULL,
            status TEXT DEFAULT 'Submitted',
            created_at TEXT NOT NULL,
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
    """)

    count = conn.execute(
        "SELECT COUNT(*) FROM jobs"
    ).fetchone()[0]

    # Clearly labelled sample jobs for the prototype.
    if count == 0:
        sample_jobs = [
            (
                "Python Developer Intern",
                "Technology",
                "Remote",
                "Internship",
                "Work on Python applications, APIs and backend development.",
                "Python, Flask, SQL, REST APIs"
            ),
            (
                "Frontend Developer Intern",
                "Technology",
                "Jaipur",
                "Internship",
                "Build responsive interfaces and interactive web applications.",
                "HTML, CSS, JavaScript, Bootstrap"
            ),
            (
                "Data Analyst Intern",
                "Analytics",
                "Remote",
                "Internship",
                "Explore datasets and create meaningful reports and dashboards.",
                "Excel, SQL, Python, Power BI"
            ),
            (
                "UI/UX Designer Intern",
                "Design",
                "Jaipur",
                "Internship",
                "Create user-friendly interfaces and improve digital experiences.",
                "Figma, Wireframing, Prototyping"
            ),
            (
                "Digital Marketing Intern",
                "Marketing",
                "Remote",
                "Internship",
                "Support digital campaigns and analyse marketing performance.",
                "SEO, Content, Social Media"
            )
        ]

        conn.executemany("""
            INSERT INTO jobs
            (title, department, location, job_type, description, requirements)
            VALUES (?, ?, ?, ?, ?, ?)
        """, sample_jobs)

    conn.commit()
    conn.close()


# ---------------- HELPER FUNCTIONS ----------------

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def valid_email(email):
    return re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+",
        email
    ) is not None


# ---------------- HOME PAGE ----------------

@app.route("/")
def index():
    search = request.args.get("search", "").strip()
    department = request.args.get("department", "").strip()
    location = request.args.get("location", "").strip()

    conn = get_db()

    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if search:
        query += " AND (title LIKE ? OR description LIKE ? OR requirements LIKE ?)"
        keyword = f"%{search}%"
        params.extend([keyword, keyword, keyword])

    if department:
        query += " AND department = ?"
        params.append(department)

    if location:
        query += " AND location = ?"
        params.append(location)

    query += " ORDER BY id DESC"

    jobs = conn.execute(query, params).fetchall()

    departments = conn.execute(
        "SELECT DISTINCT department FROM jobs ORDER BY department"
    ).fetchall()

    locations = conn.execute(
        "SELECT DISTINCT location FROM jobs ORDER BY location"
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        jobs=jobs,
        departments=departments,
        locations=locations,
        search=search,
        selected_department=department,
        selected_location=location
    )


# ---------------- JOB DETAILS ----------------

@app.route("/job/<int:job_id>")
def job_details(job_id):
    conn = get_db()

    job = conn.execute(
        "SELECT * FROM jobs WHERE id = ?",
        (job_id,)
    ).fetchone()

    conn.close()

    if job is None:
        abort(404)

    return render_template("job_details.html", job=job)


# ---------------- APPLICATION FORM ----------------

@app.route("/apply/<int:job_id>", methods=["GET", "POST"])
def apply(job_id):
    conn = get_db()

    job = conn.execute(
        "SELECT * FROM jobs WHERE id = ?",
        (job_id,)
    ).fetchone()

    conn.close()

    if job is None:
        abort(404)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        skills = request.form.get("skills", "").strip()
        introduction = request.form.get("introduction", "").strip()
        resume = request.files.get("resume")

        if not all([name, email, phone, skills, introduction]):
            flash("Please complete all required fields.", "error")
            return render_template("apply.html", job=job)

        if not valid_email(email):
            flash("Please enter a valid email address.", "error")
            return render_template("apply.html", job=job)

        if not re.fullmatch(r"[0-9+\-\s()]{7,20}", phone):
            flash("Please enter a valid phone number.", "error")
            return render_template("apply.html", job=job)

        if not resume or resume.filename == "":
            flash("Please upload your resume in PDF format.", "error")
            return render_template("apply.html", job=job)

        if not allowed_file(resume.filename):
            flash("Only PDF resumes are accepted.", "error")
            return render_template("apply.html", job=job)

        tracking_code = secrets.token_urlsafe(12)
        filename = secure_filename(
            tracking_code + ".pdf"
        )

        resume_path = os.path.join(UPLOAD_FOLDER, filename)
        resume.save(resume_path)

        conn = get_db()

        conn.execute("""
            INSERT INTO applications (
                tracking_code, job_id, name, email, phone,
                skills, introduction, resume, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tracking_code,
            job_id,
            name,
            email,
            phone,
            skills,
            introduction,
            filename,
            "Submitted",
            datetime.now().strftime("%Y-%m-%d %H:%M")
        ))

        conn.commit()
        conn.close()

        return render_template(
            "apply.html",
            job=job,
            success=True,
            tracking_code=tracking_code
        )

    return render_template("apply.html", job=job)


# ---------------- APPLICATION TRACKING ----------------

@app.route("/my-applications", methods=["GET", "POST"])
def applications():
    results = []
    searched = False

    if request.method == "POST":
        tracking_code = request.form.get(
            "tracking_code", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        if tracking_code and email:
            conn = get_db()

            results = conn.execute("""
                SELECT applications.*, jobs.title
                FROM applications
                JOIN jobs ON applications.job_id = jobs.id
                WHERE applications.tracking_code = ?
                AND applications.email = ?
            """, (tracking_code, email)).fetchall()

            conn.close()
            searched = True

    return render_template(
        "applications.html",
        results=results,
        searched=searched
    )


# ---------------- ERROR HANDLING ----------------

@app.errorhandler(404)
def not_found(error):
    return render_template(
        "base.html",
        error_message="The page or job you requested was not found."
    ), 404


@app.errorhandler(413)
def file_too_large(error):
    return "File too large. Maximum upload size is 5 MB.", 413


# ---------------- RUN APPLICATION ----------------

init_db()

if __name__ == "__main__":
    app.run(debug=True)
