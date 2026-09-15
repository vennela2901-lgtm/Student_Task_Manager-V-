from flask import Flask, render_template, request, redirect, session, Response
import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io

app = Flask(__name__)
app.secret_key = "studenttaskmanager"


def get_connection():
    return sqlite3.connect("tasks.db")


@app.route("/")
def home():
    return redirect("/login")


# =========================
# REGISTER
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if not username or not password:
            return """
            <h2>Username and password are required!</h2>
            <a href="/register">Go Back</a>
            """

        hashed_password = generate_password_hash(password)

        con = get_connection()
        cur = con.cursor()

        try:
            cur.execute(
                "INSERT INTO users(username, password) VALUES(?, ?)",
                (username, hashed_password)
            )
            con.commit()

        except sqlite3.IntegrityError:
            con.close()
            return """
            <h2>Username already exists!</h2>
            <a href="/register">Go Back</a>
            """

        con.close()

        return redirect("/login")

    return render_template("register.html")


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        con = get_connection()
        cur = con.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username=?",
            (username,)
        )

        user = cur.fetchone()

        if user:

            stored_password = user[2]

            try:
                password_correct = check_password_hash(
                    stored_password,
                    password
                )

            except ValueError:
                password_correct = False

            # Upgrade old plain-text passwords
            if not password_correct and stored_password == password:

                new_password = generate_password_hash(password)

                cur.execute(
                    "UPDATE users SET password=? WHERE username=?",
                    (new_password, username)
                )

                con.commit()

                password_correct = True

            con.close()

            if password_correct:

                session["username"] = username

                return redirect("/dashboard")

        else:
            con.close()

        return """
        <h2>Invalid Username or Password</h2>
        <a href="/login">Try Again</a>
        """

    return render_template("login.html")


# =========================
# DASHBOARD
# =========================
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():

    if "username" not in session:
        return redirect("/login")

    username = session["username"]

    con = get_connection()
    cur = con.cursor()

    # =========================
    # ADD TASK
    # =========================
    if request.method == "POST":

        task = request.form.get("task", "").strip()
        due_date = request.form.get("due_date", "")
        priority = request.form.get("priority", "Medium")
        category = request.form.get("category", "Other")

        if task:

            cur.execute("""
                INSERT INTO tasks
                (username, task, status, due_date, priority, category)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                username,
                task,
                "Pending",
                due_date,
                priority,
                category
            ))

            cur.execute("""
                INSERT INTO activity
                (username, action, task)
                VALUES (?, ?, ?)
            """, (
                username,
                "Task Added",
                task
            ))

            con.commit()

    # =========================
    # SEARCH / FILTER / SORT
    # =========================
    search = request.args.get("search", "").strip()

    filter_type = request.args.get(
        "filter",
        "all"
    )

    sort_type = request.args.get(
        "sort",
        "newest"
    )

    cur.execute(
        "SELECT * FROM tasks WHERE username=?",
        (username,)
    )

    all_tasks = cur.fetchall()

    today = date.today().isoformat()

    tasks = []

    for task_item in all_tasks:

        # Search
        if search:

            if search.lower() not in task_item[2].lower():
                continue

        # Filters
        if filter_type == "pending":

            if task_item[3] != "Pending":
                continue

        elif filter_type == "in_progress":

            if task_item[3] != "In Progress":
                continue

        elif filter_type == "completed":

            if task_item[3] != "Completed":
                continue

        elif filter_type == "high":

            if task_item[5] != "High":
                continue

        elif filter_type == "overdue":

            if task_item[3] == "Completed":
                continue

            if not task_item[4]:
                continue

            if task_item[4] >= today:
                continue

        tasks.append(task_item)

    # =========================
    # SORT
    # =========================
    if sort_type == "due":

        tasks.sort(
            key=lambda x: x[4]
            if x[4]
            else "9999-12-31"
        )

    elif sort_type == "priority":

        priority_order = {
            "High": 1,
            "Medium": 2,
            "Low": 3
        }

        tasks.sort(
            key=lambda x:
            priority_order.get(x[5], 4)
        )

    else:

        tasks.sort(
            key=lambda x: x[0],
            reverse=True
        )

    # =========================
    # STATISTICS
    # =========================
    cur.execute(
        "SELECT COUNT(*) FROM tasks WHERE username=?",
        (username,)
    )

    total = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE username=?
        AND status='Completed'
    """, (username,))

    completed = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE username=?
        AND status='Pending'
    """, (username,))

    pending = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*)
        FROM tasks
        WHERE username=?
        AND status='In Progress'
    """, (username,))

    in_progress = cur.fetchone()[0]

    # =========================
    # PROGRESS
    # =========================
    if total > 0:

        progress = int(
            (completed / total) * 100
        )

    else:

        progress = 0

    # =========================
    # CATEGORIES
    # =========================
    categories = {
        "Study": 0,
        "Coding": 0,
        "Assignment": 0,
        "Personal": 0,
        "Other": 0
    }

    for task_item in all_tasks:

        category_name = task_item[6]

        if category_name in categories:

            categories[category_name] += 1

    # =========================
    # OVERDUE / UPCOMING
    # =========================
    overdue_tasks = []
    upcoming_tasks = []

    for task_item in all_tasks:

        task_due_date = task_item[4]
        task_status = task_item[3]

        if task_due_date:

            if (
                task_status != "Completed"
                and task_due_date < today
            ):

                overdue_tasks.append(task_item)

            elif (
                task_status != "Completed"
                and task_due_date >= today
            ):

                upcoming_tasks.append(task_item)

    overdue_count = len(overdue_tasks)

    upcoming_count = len(upcoming_tasks)

    # =========================
    # ACTIVITY COUNT
    # =========================
    cur.execute("""
        SELECT COUNT(*)
        FROM activity
        WHERE username=?
    """, (username,))

    activity_count = cur.fetchone()[0]

    con.close()

    return render_template(
        "dashboard.html",
        tasks=tasks,
        username=username,
        total=total,
        completed=completed,
        pending=pending,
        in_progress=in_progress,
        search=search,
        filter_type=filter_type,
        sort_type=sort_type,
        today=today,
        progress=progress,
        categories=categories,
        overdue_tasks=overdue_tasks,
        upcoming_tasks=upcoming_tasks,
        overdue_count=overdue_count,
        upcoming_count=upcoming_count,
        activity_count=activity_count
    )


# =========================
# CHANGE TASK STATUS
# =========================
@app.route("/status/<int:id>/<status>")
def change_status(id, status):

    if "username" not in session:
        return redirect("/login")

    allowed_statuses = [
        "Pending",
        "In Progress",
        "Completed"
    ]

    if status not in allowed_statuses:
        return redirect("/dashboard")

    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        SELECT task
        FROM tasks
        WHERE id=?
        AND username=?
    """, (
        id,
        session["username"]
    ))

    task = cur.fetchone()

    if task:

        cur.execute("""
            UPDATE tasks
            SET status=?
            WHERE id=?
            AND username=?
        """, (
            status,
            id,
            session["username"]
        ))

        cur.execute("""
            INSERT INTO activity
            (username, action, task)
            VALUES (?, ?, ?)
        """, (
            session["username"],
            "Status Changed to " + status,
            task[0]
        ))

        con.commit()

    con.close()

    return redirect("/dashboard")


# =========================
# PROFILE
# =========================
@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "username" not in session:
        return redirect("/login")

    message = ""
    error = ""

    if request.method == "POST":

        current_password = request.form.get(
            "current_password",
            ""
        )

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not current_password or not new_password:

            error = "All password fields are required."

        elif new_password != confirm_password:

            error = "New passwords do not match."

        elif len(new_password) < 6:

            error = "New password must contain at least 6 characters."

        else:

            con = get_connection()
            cur = con.cursor()

            cur.execute("""
                SELECT password
                FROM users
                WHERE username=?
            """, (
                session["username"],
            ))

            user = cur.fetchone()

            if user:

                stored_password = user[0]

                try:

                    correct = check_password_hash(
                        stored_password,
                        current_password
                    )

                except ValueError:

                    correct = (
                        stored_password
                        == current_password
                    )

                if correct:

                    new_hashed_password = generate_password_hash(
                        new_password
                    )

                    cur.execute("""
                        UPDATE users
                        SET password=?
                        WHERE username=?
                    """, (
                        new_hashed_password,
                        session["username"]
                    ))

                    con.commit()

                    message = "Password changed successfully!"

                else:

                    error = "Current password is incorrect."

            else:

                error = "User not found."

            con.close()

    return render_template(
        "profile.html",
        username=session["username"],
        message=message,
        error=error
    )


# =========================
# ACTIVITY
# =========================
@app.route("/activity")
def activity():

    if "username" not in session:
        return redirect("/login")

    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        SELECT action, task, activity_time
        FROM activity
        WHERE username=?
        ORDER BY id DESC
    """, (
        session["username"],
    ))

    activities = cur.fetchall()

    con.close()

    return render_template(
        "activity.html",
        username=session["username"],
        activities=activities
    )


# =========================
# EXPORT CSV
# =========================
@app.route("/export")
def export_tasks():

    if "username" not in session:
        return redirect("/login")

    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        SELECT task, status, due_date, priority, category
        FROM tasks
        WHERE username=?
        ORDER BY id DESC
    """, (
        session["username"],
    ))

    tasks = cur.fetchall()

    con.close()

    output = io.StringIO()

    writer = csv.writer(output)

    writer.writerow([
        "Task",
        "Status",
        "Due Date",
        "Priority",
        "Category"
    ])

    for task in tasks:
        writer.writerow(task)

    csv_data = output.getvalue()

    output.close()

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition":
            "attachment; filename=student_tasks.csv"
        }
    )


# =========================
# EDIT TASK
# =========================
@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):

    if "username" not in session:
        return redirect("/login")

    con = get_connection()
    cur = con.cursor()

    if request.method == "POST":

        task = request.form.get(
            "task",
            ""
        ).strip()

        due_date = request.form.get(
            "due_date",
            ""
        )

        priority = request.form.get(
            "priority",
            "Medium"
        )

        category = request.form.get(
            "category",
            "Other"
        )

        cur.execute("""
            UPDATE tasks
            SET task=?,
                due_date=?,
                priority=?,
                category=?
            WHERE id=?
            AND username=?
        """, (
            task,
            due_date,
            priority,
            category,
            id,
            session["username"]
        ))

        cur.execute("""
            INSERT INTO activity
            (username, action, task)
            VALUES (?, ?, ?)
        """, (
            session["username"],
            "Task Edited",
            task
        ))

        con.commit()

        con.close()

        return redirect("/dashboard")

    cur.execute("""
        SELECT *
        FROM tasks
        WHERE id=?
        AND username=?
    """, (
        id,
        session["username"]
    ))

    task = cur.fetchone()

    con.close()

    if task is None:

        return """
        <h2>Task not found!</h2>
        <a href="/dashboard">
        Back to Dashboard
        </a>
        """

    return render_template(
        "edit.html",
        task=task
    )


# =========================
# DELETE TASK
# =========================
@app.route("/delete/<int:id>")
def delete(id):

    if "username" not in session:
        return redirect("/login")

    con = get_connection()
    cur = con.cursor()

    cur.execute("""
        SELECT task
        FROM tasks
        WHERE id=?
        AND username=?
    """, (
        id,
        session["username"]
    ))

    task = cur.fetchone()

    if task:

        cur.execute("""
            DELETE FROM tasks
            WHERE id=?
            AND username=?
        """, (
            id,
            session["username"]
        ))

        cur.execute("""
            INSERT INTO activity
            (username, action, task)
            VALUES (?, ?, ?)
        """, (
            session["username"],
            "Task Deleted",
            task[0]
        ))

    con.commit()

    con.close()

    return redirect("/dashboard")


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================
# RUN APPLICATION
# =========================
if __name__ == "__main__":
    app.run(debug=True)