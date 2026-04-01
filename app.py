import sqlite3
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = "safelink_secret_key"
DATABASE = "database.db"


# -------------------- DATABASE CONNECTION --------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------- CREATE TABLES --------------------
def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pair_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS paired_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_id INTEGER NOT NULL,
            user2_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Active'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS live_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sos_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            alert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # ADD THIS inside init_db(), after other CREATE TABLES
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sharing_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            is_sharing INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# -------------------- LOGIN REQUIRED DECORATOR --------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# -------------------- HOME --------------------
@app.route("/")
def index():
    return render_template("index.html")


# -------------------- REGISTER --------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        phone = request.form["phone"].strip()
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()

        try:
            cur.execute(
                "INSERT INTO users (name, phone, email, password) VALUES (?, ?, ?, ?)",
                (name, phone, email, hashed_password)
            )
            conn.commit()
            flash("Registration successful. Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Phone number or email already exists.", "danger")
        finally:
            conn.close()

    return render_template("register.html")


# -------------------- LOGIN --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form["identifier"].strip()
        password = request.form["password"].strip()

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE phone = ? OR email = ?",
            (identifier, identifier)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid login credentials.", "danger")

    return render_template("login.html")


# -------------------- LOGOUT --------------------
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# -------------------- DASHBOARD --------------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    conn = get_db_connection()

    paired_user = conn.execute("""
        SELECT u.id, u.name, u.phone, u.email
        FROM paired_users p
        JOIN users u 
            ON (u.id = p.user1_id OR u.id = p.user2_id)
        WHERE (p.user1_id = ? OR p.user2_id = ?)
          AND u.id != ?
          AND p.status = 'Active'
        LIMIT 1
    """, (user_id, user_id, user_id)).fetchone()

    conn.close()
    return render_template("dashboard.html", paired_user=paired_user)
@app.route("/start-sharing", methods=["POST"])
@login_required
def start_sharing():
    user_id = session["user_id"]
    conn = get_db_connection()

    existing = conn.execute(
        "SELECT * FROM sharing_status WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE sharing_status
            SET is_sharing = 1, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))
    else:
        conn.execute("""
            INSERT INTO sharing_status (user_id, is_sharing)
            VALUES (?, 1)
        """, (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Sharing started"})


@app.route("/stop-sharing", methods=["POST"])
@login_required
def stop_sharing():
    user_id = session["user_id"]
    conn = get_db_connection()

    existing = conn.execute(
        "SELECT * FROM sharing_status WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if existing:
        conn.execute("""
            UPDATE sharing_status
            SET is_sharing = 0, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (user_id,))
    else:
        conn.execute("""
            INSERT INTO sharing_status (user_id, is_sharing)
            VALUES (?, 0)
        """, (user_id,))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Sharing stopped"})


@app.route("/get-sharing-status")
@login_required
def get_sharing_status():
    user_id = session["user_id"]
    conn = get_db_connection()

    row = conn.execute("""
        SELECT is_sharing, updated_at
        FROM sharing_status
        WHERE user_id = ?
    """, (user_id,)).fetchone()

    conn.close()

    if row:
        return jsonify({
            "success": True,
            "is_sharing": bool(row["is_sharing"]),
            "updated_at": row["updated_at"]
        })

    return jsonify({
        "success": True,
        "is_sharing": False,
        "updated_at": None
    })

# -------------------- SEND PAIR REQUEST --------------------
@app.route("/send-request", methods=["GET", "POST"])
@login_required
def send_request():
    if request.method == "POST":
        receiver_input = request.form["receiver"].strip()
        sender_id = session["user_id"]

        conn = get_db_connection()
        receiver = conn.execute(
            "SELECT * FROM users WHERE phone = ? OR email = ?",
            (receiver_input, receiver_input)
        ).fetchone()

        if not receiver:
            conn.close()
            flash("User not found.", "danger")
            return redirect(url_for("send_request"))

        if receiver["id"] == sender_id:
            conn.close()
            flash("You cannot send a request to yourself.", "warning")
            return redirect(url_for("send_request"))

        existing_pair = conn.execute("""
            SELECT * FROM paired_users
            WHERE ((user1_id = ? AND user2_id = ?) OR (user1_id = ? AND user2_id = ?))
              AND status = 'Active'
        """, (sender_id, receiver["id"], receiver["id"], sender_id)).fetchone()

        if existing_pair:
            conn.close()
            flash("You are already paired with this user.", "info")
            return redirect(url_for("dashboard"))

        existing_request = conn.execute("""
            SELECT * FROM pair_requests
            WHERE ((sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?))
              AND status = 'Pending'
        """, (sender_id, receiver["id"], receiver["id"], sender_id)).fetchone()

        if existing_request:
            conn.close()
            flash("A pending request already exists.", "warning")
            return redirect(url_for("dashboard"))

        conn.execute("""
            INSERT INTO pair_requests (sender_id, receiver_id, status)
            VALUES (?, ?, 'Pending')
        """, (sender_id, receiver["id"]))
        conn.commit()
        conn.close()

        flash("Pair request sent successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("send_request.html")


# -------------------- VIEW PAIR REQUESTS --------------------
@app.route("/pair-requests")
@login_required
def pair_requests():
    user_id = session["user_id"]
    conn = get_db_connection()

    requests_list = conn.execute("""
        SELECT pr.id, pr.status, pr.created_at, u.name AS sender_name, u.phone AS sender_phone, u.email AS sender_email
        FROM pair_requests pr
        JOIN users u ON pr.sender_id = u.id
        WHERE pr.receiver_id = ? AND pr.status = 'Pending'
        ORDER BY pr.id DESC
    """, (user_id,)).fetchall()

    conn.close()
    return render_template("pair_requests.html", requests_list=requests_list)


# -------------------- ACCEPT PAIR REQUEST --------------------
@app.route("/accept-request/<int:request_id>")
@login_required
def accept_request(request_id):
    user_id = session["user_id"]
    conn = get_db_connection()

    pair_request = conn.execute("""
        SELECT * FROM pair_requests
        WHERE id = ? AND receiver_id = ? AND status = 'Pending'
    """, (request_id, user_id)).fetchone()

    if not pair_request:
        conn.close()
        flash("Invalid request.", "danger")
        return redirect(url_for("pair_requests"))

    sender_id = pair_request["sender_id"]

    conn.execute("""
        INSERT INTO paired_users (user1_id, user2_id, status)
        VALUES (?, ?, 'Active')
    """, (sender_id, user_id))

    conn.execute("""
        UPDATE pair_requests
        SET status = 'Accepted'
        WHERE id = ?
    """, (request_id,))

    conn.commit()
    conn.close()

    flash("Pair request accepted.", "success")
    return redirect(url_for("dashboard"))


# -------------------- REJECT PAIR REQUEST --------------------
@app.route("/reject-request/<int:request_id>")
@login_required
def reject_request(request_id):
    user_id = session["user_id"]
    conn = get_db_connection()

    pair_request = conn.execute("""
        SELECT * FROM pair_requests
        WHERE id = ? AND receiver_id = ? AND status = 'Pending'
    """, (request_id, user_id)).fetchone()

    if not pair_request:
        conn.close()
        flash("Invalid request.", "danger")
        return redirect(url_for("pair_requests"))

    conn.execute("""
        UPDATE pair_requests
        SET status = 'Rejected'
        WHERE id = ?
    """, (request_id,))
    conn.commit()
    conn.close()

    flash("Pair request rejected.", "info")
    return redirect(url_for("pair_requests"))


# -------------------- UPDATE LIVE LOCATION --------------------
@app.route("/update-location", methods=["POST"])
@login_required
def update_location():
    user_id = session["user_id"]

    data = request.get_json()
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        return jsonify({"success": False, "message": "Invalid location data"}), 400

    conn = get_db_connection()

    existing = conn.execute("""
        SELECT * FROM live_locations WHERE user_id = ?
    """, (user_id,)).fetchone()

    if existing:
        conn.execute("""
            UPDATE live_locations
            SET latitude = ?, longitude = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (latitude, longitude, user_id))
    else:
        conn.execute("""
            INSERT INTO live_locations (user_id, latitude, longitude)
            VALUES (?, ?, ?)
        """, (user_id, latitude, longitude))

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Location updated successfully"})


# -------------------- VIEW PAIRED USER LOCATION --------------------
@app.route("/view-location")
@login_required
def view_location():
    user_id = session["user_id"]
    conn = get_db_connection()

    paired_user = conn.execute("""
        SELECT u.id, u.name
        FROM paired_users p
        JOIN users u 
            ON (u.id = p.user1_id OR u.id = p.user2_id)
        WHERE (p.user1_id = ? OR p.user2_id = ?)
          AND u.id != ?
          AND p.status = 'Active'
        LIMIT 1
    """, (user_id, user_id, user_id)).fetchone()

    if not paired_user:
        conn.close()
        flash("No paired user found.", "warning")
        return redirect(url_for("dashboard"))

    live_location = conn.execute("""
        SELECT latitude, longitude, updated_at
        FROM live_locations
        WHERE user_id = ?
    """, (paired_user["id"],)).fetchone()

    conn.close()

    return render_template(
        "map_view.html",
        paired_user=paired_user,
        live_location=live_location
    )


# -------------------- GET LOCATION API FOR AUTO REFRESH --------------------
@app.route("/get-paired-location")
@login_required
def get_paired_location():
    user_id = session["user_id"]
    conn = get_db_connection()

    paired_user = conn.execute("""
        SELECT u.id, u.name
        FROM paired_users p
        JOIN users u 
            ON (u.id = p.user1_id OR u.id = p.user2_id)
        WHERE (p.user1_id = ? OR p.user2_id = ?)
          AND u.id != ?
          AND p.status = 'Active'
        LIMIT 1
    """, (user_id, user_id, user_id)).fetchone()

    if not paired_user:
        conn.close()
        return jsonify({"success": False, "message": "No paired user found"})

    live_location = conn.execute("""
        SELECT latitude, longitude, updated_at
        FROM live_locations
        WHERE user_id = ?
    """, (paired_user["id"],)).fetchone()

    conn.close()

    if not live_location:
        return jsonify({"success": False, "message": "No location available"})

    return jsonify({
        "success": True,
        "name": paired_user["name"],
        "latitude": live_location["latitude"],
        "longitude": live_location["longitude"],
        "updated_at": live_location["updated_at"]
    })


# -------------------- SEND SOS --------------------
@app.route("/send-sos", methods=["POST"])
@login_required
def send_sos():
    user_id = session["user_id"]
    data = request.get_json()

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        return jsonify({"success": False, "message": "Invalid SOS location"}), 400

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO sos_alerts (user_id, latitude, longitude)
        VALUES (?, ?, ?)
    """, (user_id, latitude, longitude))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "SOS alert sent successfully"})


# -------------------- VIEW SOS ALERTS --------------------
@app.route("/view-sos")
@login_required
def view_sos():
    user_id = session["user_id"]
    conn = get_db_connection()

    paired_user = conn.execute("""
        SELECT u.id, u.name
        FROM paired_users p
        JOIN users u 
            ON (u.id = p.user1_id OR u.id = p.user2_id)
        WHERE (p.user1_id = ? OR p.user2_id = ?)
          AND u.id != ?
          AND p.status = 'Active'
        LIMIT 1
    """, (user_id, user_id, user_id)).fetchone()

    if not paired_user:
        conn.close()
        flash("No paired user found.", "warning")
        return redirect(url_for("dashboard"))

    alerts = conn.execute("""
        SELECT * FROM sos_alerts
        WHERE user_id = ?
        ORDER BY id DESC
    """, (paired_user["id"],)).fetchall()

    conn.close()
    return render_template("sos_alerts.html", alerts=alerts, paired_user=paired_user)


# -------------------- RUN APP --------------------
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)