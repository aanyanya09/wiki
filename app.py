from flask import Flask, render_template,request,url_for,redirect,session,flash
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
import os
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me")


Database = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wiki_database.db')
def get_db_connection():
    con=sqlite3.connect(Database)
    con.row_factory=sqlite3.Row
    return con

MAX_UPDATES = 3

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        con = get_db_connection()
        user = con.execute("SELECT role FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        con.close()
        if user is None or user['role'] != 'admin':
            flash("Admins only.")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/')
def login_page():
    return render_template('index.html') 

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
      return redirect(url_for('login_page'))
    current_user_id = session['user_id']
    con = get_db_connection()
    projects = con.execute("SELECT * FROM projects ORDER BY rowid DESC").fetchall()
    incoming_requests = con.execute('''
        SELECT users.username AS applicant_name, users.role AS applicant_role, 
               users.email AS applicant_email, projects.project_name, projects.id AS project_id
        FROM join_requests
        INNER JOIN users ON join_requests.applicant_id = users.id
        INNER JOIN projects ON join_requests.project_id = projects.id
        WHERE projects.user_id = ? AND join_requests.status = 'pending'
    ''', (current_user_id,)).fetchall()
    con.close()
    return render_template('dashboard.html', projects=projects, requests=incoming_requests)

ALLOWED_ROLES = {'Developer', 'Designer', 'Student', 'Mentor'}
ALLOWED_LEVELS = {'Beginner', 'Intermediate', 'Advanced'}
@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        email=request.form.get('email')
        username=request.form.get('username')
        password=request.form.get('password')
        confirm_password=request.form.get('confirm_password')
        skills=request.form.get('skills')
        experience_level=request.form.get('experience_level')
        role = request.form.get('role')

        if password!=confirm_password:
            flash("password do not match!")
            return redirect(url_for('register'))

        if role not in ALLOWED_ROLES:
            flash("Invalid role selected.")
            return redirect(url_for('register'))

        if experience_level not in ALLOWED_LEVELS:
            flash("Invalid experience level.")
            return redirect(url_for('register'))
        
        hashed = generate_password_hash(password) 

        con=get_db_connection()
        try:
            con.execute("""insert into users(username,password,email,role,skills,experience_level)values(?,?,?,?,?,?)""",(username,hashed,email,role,skills,experience_level))
            con.commit()
            return redirect(url_for('login_page'))
        except sqlite3.IntegrityError as e:
            print("REGISTER ERROR:", e)
            flash(f"Could not register: {e}")
            return redirect(url_for('register'))
        finally:
            con.close()
    return render_template('register.html')


@app.route('/login',methods=['POST'])
def login():
    username=request.form.get('username')
    password=request.form.get('password')
    con=get_db_connection()
    user=con.execute("SELECT * FROM users WHERE username=?",(username,)).fetchone()
    con.close()
    
    if user and check_password_hash(user['password'],password):
         session['username'] = username
         session['user_id'] = user['id']
         return redirect(url_for('dashboard'))

    return "Invalid credentials"

   

@app.route('/project_details',methods=['GET','POST','PATCH'])
def project_details():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    if request.method=='POST':
        project_name = request.form['project_name']
        project_description=request.form['project_description']
        project_status = int(request.form['project_status'])
        skills_needed = request.form['skills_needed']
        total_member_required=int(request.form['total_member_required'])
        contact_link = request.form['contact_link']
        current_user_id = session['user_id'] # Links project directly to active User ID
        
        con = get_db_connection()
        con.execute(
            """INSERT INTO projects (project_name,project_description, project_status, skills_needed, total_member_required, contact_link, user_id) 
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (project_name,project_description, project_status, skills_needed, total_member_required,contact_link, current_user_id)
        )
        con.commit()
        con.close()
        flash("Project successfully posted!")
        return redirect(url_for('dashboard'))

    return render_template('project_details.html')

@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    con = get_db_connection()
    project = con.execute(
        "SELECT * FROM projects WHERE id = ? AND user_id = ?",
        (project_id, session['user_id'])
    ).fetchone()

    if project is None:
        con.close()
        flash("Project not found or you don't have permission.")
        return redirect(url_for('dashboard'))

    if project['update_count'] >= MAX_UPDATES:
        con.close()
        flash("This project has reached the maximum of 3 updates.")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        cur = con.execute(
            """UPDATE projects
               SET skills_needed = ?, total_member_required = ?,
                   update_count = update_count + 1
               WHERE id = ? AND user_id = ? AND update_count < ?""",
            (request.form['skills_needed'], int(request.form['total_member_required']),
             project_id, session['user_id'], MAX_UPDATES)
        )
        con.commit()
        con.close()
        flash("Project updated successfully!" if cur.rowcount else "Update limit reached.")
        return redirect(url_for('dashboard'))

    remaining = MAX_UPDATES - project['update_count']
    con.close()
    return render_template('edit_project.html', project=project, remaining=remaining)


@app.route('/projects')
def projects():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
        
    con = get_db_connection()
  
    projects = con.execute('SELECT * FROM projects').fetchall()
    con.close()
    
    return render_template('projects.html', projects=projects)


@app.context_processor
def inject_counts():
   
    try:
        con = get_db_connection()
        pc = con.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        mc = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        con.close()
    except sqlite3.Error:
        pc, mc = 0, 0
    return dict(project_count=pc, member_count=mc)

@app.context_processor
def inject_current_user():
    if 'user_id' not in session:
        return dict(current_user=None)
    con = get_db_connection()
    user = con.execute(
        "SELECT id, username, role FROM users WHERE id = ?", (session['user_id'],)
    ).fetchone()
    con.close()
    return dict(current_user=user)


@app.route('/members')
def members():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    con = get_db_connection()
    users = con.execute("""
        SELECT id, username, role, skills, experience_level,
           (last_seen >= datetime('now', '-5 minutes')) AS is_online
        FROM users ORDER BY username
    """).fetchall()
    con.close()
    return render_template('members.html', users=users)

@app.route('/admin/member/<int:member_id>/delete', methods=['POST'])
@admin_required
def admin_delete_member(member_id):
    if member_id == session['user_id']:
        flash("You can't delete your own account.")
        return redirect(url_for('members'))

    con = get_db_connection()
    target = con.execute("SELECT role FROM users WHERE id = ?", (member_id,)).fetchone()
    if target is None:
        con.close()
        flash("Member not found.")
        return redirect(url_for('members'))
    if target['role'] == 'admin':
        con.close()
        flash("You can't delete another admin.")
        return redirect(url_for('members'))

    con.execute("""DELETE FROM join_requests
                   WHERE applicant_id = ?
                      OR project_id IN (SELECT id FROM projects WHERE user_id = ?)""",
                (member_id, member_id))
    con.execute("DELETE FROM projects WHERE user_id = ?", (member_id,))
    con.execute("DELETE FROM users WHERE id = ?", (member_id,))
    con.commit()
    con.close()
    flash("Member deleted.")
    return redirect(url_for('members'))

@app.route('/admin/member/<int:member_id>/toggle_admin', methods=['POST'])
@admin_required
def toggle_admin(member_id):
    if member_id == session['user_id']:
        flash("You can't change your own admin status.")
        return redirect(url_for('members'))

    con = get_db_connection()
    target = con.execute("SELECT role FROM users WHERE id = ?", (member_id,)).fetchone()
    if target is None:
        con.close()
        flash("Member not found.")
        return redirect(url_for('members'))

    if target['role'] == 'admin':
        new_role = 'Developer'   # role given back when demoted
        msg = "Admin rights removed."
    else:
        new_role = 'admin'
        msg = "Member promoted to admin."

    con.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, member_id))
    con.commit()
    con.close()
    flash(msg)
    return redirect(url_for('members'))

@app.route('/logout')
def logout():
  
    session.pop('username', None)
    session.pop('user_id', None)
    
  
    return redirect(url_for('login_page'))


@app.route("/request_join/<int:project_id>", methods=["POST"])
def request_join(project_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    applicant_id = session["user_id"]
    con = get_db_connection()

  
    project = con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if project is None:
        con.close()
        return "Project not found", 404

  
    existing = con.execute(
        "SELECT 1 FROM join_requests WHERE project_id=? AND applicant_id=?",
        (project_id, applicant_id)
    ).fetchone()
    if existing:
        con.close()
        flash("You already requested to join this project.")
        return redirect(url_for("projects"))

   
    if project["user_id"] == applicant_id:
        con.close()
        flash("You can't join your own project.")
        return redirect(url_for("projects"))


    con.execute(
        "INSERT INTO join_requests (project_id, applicant_id, status) VALUES (?, ?, ?)",
        (project_id, applicant_id, "pending")
    )
    con.commit()
    con.close()

    flash("Join request sent successfully!")
    return redirect(url_for("projects"))

@app.route("/view_project/<int:project_id>", methods=["GET"])
def view_project(project_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))
    current_user_id=session["user_id"]
    con=get_db_connection()
    projects=con.execute("select * from projects where id=?",(project_id,)).fetchone()
    con.close()
    if projects is None:
        return "Project not found", 404
    return render_template("view_projects.html",project=projects)


@app.route("/project_requests/<int:project_id>")
def project_requests(project_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    con = get_db_connection()
    project = con.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    
    if project is None:
        con.close()
        return "Project not found", 404
    if project["user_id"] != session["user_id"]:
        con.close()
        return "Unauthorized", 403

   
    requests = con.execute("""
        SELECT join_requests.id, join_requests.status, users.username, users.email, users.skills, users.experience_level
        FROM join_requests
        JOIN users ON join_requests.applicant_id = users.id
        WHERE join_requests.project_id = ?
    """, (project_id,)).fetchall()
    con.close()

    return render_template("project_requests.html", project=project, requests=requests)

@app.route("/accept_request/<int:request_id>", methods=["POST"])
def accept_request(request_id):
    return update_request_status(request_id, "accepted")


@app.route("/reject_request/<int:request_id>", methods=["POST"])
def reject_request(request_id):
    return update_request_status(request_id, "rejected")


def update_request_status(request_id, new_status):
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    con = get_db_connection()
    req = con.execute("""
        SELECT join_requests.project_id, projects.user_id AS owner_id
        FROM join_requests
        JOIN projects ON join_requests.project_id = projects.id
        WHERE join_requests.id = ?
    """, (request_id,)).fetchone()

    if req is None:
        con.close()
        return "Request not found", 404
    if req["owner_id"] != session["user_id"]:
        con.close()
        return "Unauthorized", 403

    con.execute("UPDATE join_requests SET status = ? WHERE id = ?", (new_status, request_id))
    con.commit()
    con.close()

    flash(f"Request {new_status}.")
    return redirect(url_for("project_requests", project_id=req["project_id"]))

@app.route("/remove_member/<int:request_id>", methods=["POST"])
def remove_member(request_id):
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    con = get_db_connection()
    req = con.execute("""
        SELECT join_requests.project_id, projects.user_id AS owner_id
        FROM join_requests
        JOIN projects ON join_requests.project_id = projects.id
        WHERE join_requests.id = ?
    """, (request_id,)).fetchone()

    if req is None:
        con.close()
        return "Request not found", 404
    if req["owner_id"] != session["user_id"]:
        con.close()
        return "Unauthorized", 403

    con.execute("DELETE FROM join_requests WHERE id = ?", (request_id,))
    con.commit()
    con.close()
    flash("Member removed.")
    return redirect(url_for("project_requests", project_id=req["project_id"]))


@app.route("/my_requests")
def my_requests():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    con = get_db_connection()
    requests = con.execute("""
        SELECT join_requests.status, projects.project_name, projects.contact_link
        FROM join_requests
        JOIN projects ON join_requests.project_id = projects.id
        WHERE join_requests.applicant_id = ?
        ORDER BY join_requests.id DESC
    """, (session["user_id"],)).fetchall()
    con.close()

    return render_template("my_requests.html", requests=requests)

@app.before_request
def update_last_seen():
    if request.endpoint == 'static':
        return
    if 'user_id' in session:
        con = get_db_connection()
        con.execute("UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?", (session['user_id'],))
        con.commit()
        con.close()



if __name__ == '__main__':
    app.run(debug=True, port=8080)
