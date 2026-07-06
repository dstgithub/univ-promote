from flask import (
    Flask,
    jsonify,
    request,
    render_template,
    redirect,
    Response,
    session,
    send_from_directory
)
import sqlite3
from functools import wraps
import os
from io import StringIO
from io import BytesIO
from werkzeug.utils import secure_filename
import uuid
import csv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = "replace-with-a-random-secret-key"

# -----------------------------
# Application configuration
# -----------------------------

DATABASE = "promote.db"

UPLOAD_FOLDER = "uploads"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "username" not in session:
                return redirect("/login")
            if session["role"] not in roles:
                return "Access denied", 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_db()

    # Create promotion_cases table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS promotion_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faculty_id INTEGER,
    title TEXT,
    statement TEXT,
    status TEXT,
    reviewer_comments TEXT,
    submitted_by TEXT,
    file_name TEXT
    )
    """)

    # Create users table
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # Insert sample users
    conn.execute("""
    INSERT OR IGNORE INTO users
    (username, password, role)
    VALUES
    ('alice', 'password', 'faculty')
    """)

    conn.execute("""
    INSERT OR IGNORE INTO users
    (username, password, role)
    VALUES
    ('bob', 'password', 'reviewer')
    """)

    conn.execute("""
    INSERT OR IGNORE INTO users
    (username, password, role)
    VALUES
    ('admin', 'password', 'admin')
    """)

    conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        conn = get_db()

        user = conn.execute(
            """
            SELECT *
            FROM users
            WHERE username=?
            AND password=?
            """,
            (
                request.form["username"],
                request.form["password"]
            )
        ).fetchone()

        if user:

            session["username"] = user["username"]
            session["role"] = user["role"]

            return redirect("/")

        return "Invalid login"

    return render_template("login.html")

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")

@app.route("/submit", methods=["GET", "POST"])
@require_role("faculty", "admin")
def submit():

    # Show the submission form
    if request.method == "GET":
        return render_template("submit.html")

    # ----------------------------
    # Handle uploaded CV
    # ----------------------------

    uploaded_file = request.files.get("cv")

    filename = None

    if uploaded_file and uploaded_file.filename != "":

        # Create a unique filename
        filename = (
            str(uuid.uuid4())
            + "_"
            + secure_filename(uploaded_file.filename)
        )

        uploaded_file.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )
        )

    # ----------------------------
    # Save case to database
    # ----------------------------

    conn = get_db()

    cursor = conn.execute("""
        INSERT INTO promotion_cases
        (
            faculty_id,
            title,
            statement,
            status,
            submitted_by,
            file_name
        )
        VALUES
        (?, ?, ?, ?, ?, ?)
        """,
        (
            request.form["faculty_id"],
            request.form["title"],
            request.form["statement"],
            "Submitted",
            session["username"],
            filename
        )
    )

    case_id = cursor.lastrowid

    conn.commit()
    conn.close()

    # ----------------------------
    # Confirmation page
    # ----------------------------

    return render_template(
        "submit_success.html",
        case_id=case_id,
        faculty_id=request.form["faculty_id"],
        title=request.form["title"],
        filename=filename
    )

@app.route("/uploads/<filename>")
@require_role("reviewer", "admin")
def uploaded_file(filename):
    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )
    
@app.route("/cases")
def cases():

    # Require login
    if "username" not in session:
        return redirect("/login")

    # Only reviewers and admins may view cases
    if session["role"] not in ("reviewer", "admin"):
        return "Access denied", 403

    conn = get_db()

    faculty_id = request.args.get("faculty_id")
    status = request.args.get("status")

    sql = "SELECT * FROM promotion_cases WHERE 1=1"
    params = []

    if faculty_id:
        sql += " AND faculty_id = ?"
        params.append(faculty_id)

    if status:
        sql += " AND status = ?"
        params.append(status)

    rows = conn.execute(sql, params).fetchall()

    conn.close()

    return render_template(
        "cases.html",
        cases=rows
    )

@app.route("/my_cases")
@require_role("faculty", "admin")
def my_cases():

    conn = get_db()

    username = session["username"]

    rows = conn.execute("""
        SELECT *
        FROM promotion_cases
        WHERE submitted_by = ?
    """, (username,)).fetchall()

    conn.close()

    return render_template(
        "my_cases.html",
        cases=rows
    )

@app.route("/review/<int:id>", methods=["POST"])
def review(id):

    data = request.json

    conn = get_db()

    conn.execute("""
    UPDATE promotion_cases
    SET
        status=?,
        reviewer_comments=?
    WHERE id=?
    """,
    (
        data["status"],
        data["comments"],
        id
    ))

    conn.commit()

    return jsonify({"message": "Updated"})

@app.route("/case/<int:case_id>", methods=["GET", "POST"])
@require_role("reviewer", "admin")
def case_detail(case_id):

    conn = get_db()

    # GET → show case
    if request.method == "GET":

        case = conn.execute("""
            SELECT *
            FROM promotion_cases
            WHERE id = ?
        """, (case_id,)).fetchone()

        conn.close()

        return render_template(
            "case_detail.html",
            case=case
        )

    # POST → update case
    status = request.form["status"]
    comments = request.form["comments"]

    conn.execute("""
        UPDATE promotion_cases
        SET status = ?, reviewer_comments = ?
        WHERE id = ?
    """,
    (status, comments, case_id))

    conn.commit()
    conn.close()

    return redirect("/cases")

@app.route("/admin/users")
@require_role("admin")
def view_users():

    conn = get_db()

    users = conn.execute("""
        SELECT id,
               username,
               role
        FROM users
        ORDER BY username
    """).fetchall()

    conn.close()

    return render_template(
        "users.html",
        users=users
    )
    
@app.route("/admin/users/add", methods=["GET", "POST"])
@require_role("admin")
def add_user():

    if request.method == "GET":
        return render_template("add_user.html")

    conn = get_db()

    conn.execute("""
        INSERT INTO users
        (username, password, role)
        VALUES (?, ?, ?)
    """,
    (
        request.form["username"],
        request.form["password"],
        request.form["role"]
    ))

    conn.commit()
    conn.close()

    return redirect("/admin/users")
    
@app.route("/admin/users/edit/<int:user_id>", methods=["GET", "POST"])
@require_role("admin")
def edit_user(user_id):

    conn = get_db()

    if request.method == "GET":

        user = conn.execute("""
            SELECT *
            FROM users
            WHERE id = ?
        """, (user_id,)).fetchone()

        conn.close()

        return render_template(
            "edit_user.html",
            user=user
        )

    conn.execute("""
        UPDATE users
        SET
            password = ?,
            role = ?
        WHERE id = ?
    """,
    (
        request.form["password"],
        request.form["role"],
        user_id
    ))

    conn.commit()
    conn.close()

    return redirect("/admin/users")

@app.route("/dashboard")
@require_role("reviewer", "admin")
def dashboard():

    conn = get_db()

    # ----------------------------
    # Summary statistics
    # ----------------------------

    total_cases = conn.execute("""
        SELECT COUNT(*)
        FROM promotion_cases
    """).fetchone()[0]

    submitted = conn.execute("""
        SELECT COUNT(*)
        FROM promotion_cases
        WHERE status='Submitted'
    """).fetchone()[0]

    approved = conn.execute("""
        SELECT COUNT(*)
        FROM promotion_cases
        WHERE status='Approved'
    """).fetchone()[0]

    rejected = conn.execute("""
        SELECT COUNT(*)
        FROM promotion_cases
        WHERE status='Rejected'
    """).fetchone()[0]

    # ----------------------------
    # Recent cases
    # ----------------------------

    recent_cases = conn.execute("""
        SELECT *
        FROM promotion_cases
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    # ----------------------------
    # Cases submitted by faculty
    # ----------------------------

    faculty_counts = conn.execute("""
        SELECT
            submitted_by,
            COUNT(*) AS total
        FROM promotion_cases
        GROUP BY submitted_by
        ORDER BY total DESC
    """).fetchall()

    conn.close()

    return render_template(

        "dashboard.html",

        # KPI cards
        total_cases=total_cases,
        submitted=submitted,
        approved=approved,
        rejected=rejected,

        # Recent table
        recent_cases=recent_cases,

        # Pie / Status Bar charts
        chart_labels=[
            "Submitted",
            "Approved",
            "Rejected"
        ],

        chart_values=[
            submitted,
            approved,
            rejected
        ],

        # Faculty chart
        faculty_labels=[
            row["submitted_by"]
            for row in faculty_counts
        ],

        faculty_values=[
            row["total"]
            for row in faculty_counts
        ]

    )

@app.route("/export/csv")
@require_role("reviewer", "admin")
def export_csv():

    conn = get_db()

    rows = conn.execute("""
        SELECT id, faculty_id, title, status, reviewer_comments
        FROM promotion_cases
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    output = StringIO()
    writer = csv.writer(output)

    # header
    writer.writerow(["id", "faculty_id", "title", "status", "reviewer_comments"])

    # data rows
    for r in rows:
        writer.writerow([
            r["id"],
            r["faculty_id"],
            r["title"],
            r["status"],
            r["reviewer_comments"] or ""
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=cases_report.csv"}
    )

@app.route("/export/pdf")
@require_role("reviewer", "admin")
def export_pdf():

    conn = get_db()

    # ----------------------------
    # Summary statistics
    # ----------------------------

    total = conn.execute("""
        SELECT COUNT(*)
        FROM promotion_cases
    """).fetchone()[0]

    submitted = conn.execute("""
        SELECT COUNT(*)
        FROM promotion_cases
        WHERE status='Submitted'
    """).fetchone()[0]

    approved = conn.execute("""
        SELECT COUNT(*)
        FROM promotion_cases
        WHERE status='Approved'
    """).fetchone()[0]

    rejected = conn.execute("""
        SELECT COUNT(*)
        FROM promotion_cases
        WHERE status='Rejected'
    """).fetchone()[0]

    # Optional: recent cases
    recent = conn.execute("""
        SELECT id, faculty_id, title, status
        FROM promotion_cases
        ORDER BY id DESC
        LIMIT 5
    """).fetchall()

    conn.close()

    # ----------------------------
    # Create PDF
    # ----------------------------

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    y = 750

    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, "Promotion System - Dashboard Report")

    y -= 40

    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Total Cases: {total}")
    y -= 20
    p.drawString(50, y, f"Submitted: {submitted}")
    y -= 20
    p.drawString(50, y, f"Approved: {approved}")
    y -= 20
    p.drawString(50, y, f"Rejected: {rejected}")

    y -= 40

    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, y, "Recent Cases")
    y -= 25

    p.setFont("Helvetica", 10)

    for r in recent:
        line = f"ID:{r['id']} | Faculty:{r['faculty_id']} | {r['title']} | {r['status']}"
        p.drawString(50, y, line)
        y -= 15

        if y < 50:
            p.showPage()
            y = 750

    p.showPage()
    p.save()

    buffer.seek(0)

    return Response(
        buffer,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=dashboard_report.pdf"
        }
    )


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)