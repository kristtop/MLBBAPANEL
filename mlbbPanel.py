from flask import Flask, request, jsonify, render_template_string
import os
import sqlite3
import time
import random
import string

app = Flask(__name__)
DB_FILE = "slider_vip.db"

# =========================
# DATABASE
# =========================
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keys_table (
            license_key TEXT PRIMARY KEY,
            hwid TEXT,
            expiry_timestamp INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# =========================
# HTML PANEL
# =========================
HTML_TEMPLATE = """ (YOUR SAME HTML HERE) """

# =========================
# DASHBOARD
# =========================
@app.route('/', methods=['GET'])
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT license_key, hwid, expiry_timestamp FROM keys_table ORDER BY expiry_timestamp DESC")
    keys = cursor.fetchall()
    conn.close()

    def datetime_format(timestamp):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))

    return render_template_string(
        HTML_TEMPLATE,
        keys=keys,
        current_time=int(time.time()),
        datetime_format=datetime_format
    )

# =========================
# GENERATE KEY
# =========================
@app.route('/admin/generate', methods=['POST'])
def admin_generate():
    duration = int(request.form.get('duration', 1))
    time_type = request.form.get('time_type', 'days')

    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=14))

    if time_type == "minutes":
        expiry_seconds = duration * 60
        prefix = f"Slider_{duration}m"
    elif time_type == "hours":
        expiry_seconds = duration * 3600
        prefix = f"Slider_{duration}h"
    else:
        expiry_seconds = duration * 86400
        prefix = f"Slider_{duration}d"

    new_key = prefix + random_str
    expiry_time = int(time.time()) + expiry_seconds

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO keys_table (license_key, hwid, expiry_timestamp) VALUES (?, '', ?)",
        (new_key, expiry_time)
    )
    conn.commit()
    conn.close()

    return f'<script>alert("Generated Key:\\n\\n{new_key}");window.location.href="/";</script>'

# =========================
# RESET HWID
# =========================
@app.route('/admin/reset/<string:key>', methods=['GET'])
def admin_reset_hwid(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE keys_table SET hwid = '' WHERE license_key = ?", (key,))
    conn.commit()
    conn.close()
    return f'<script>alert("HWID Reset Success\\n\\n{key}");window.location.href="/";</script>'

# =========================
# DELETE KEY
# =========================
@app.route('/admin/delete/<string:key>', methods=['GET'])
def admin_delete_key(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keys_table WHERE license_key = ?", (key,))
    conn.commit()
    conn.close()
    return f'<script>alert("Deleted Key\\n\\n{key}");window.location.href="/";</script>'

# =========================
# VERIFY API
# =========================
@app.route('/verify', methods=['POST'])
def verify_key():
    key = request.form.get('key')
    hwid = request.form.get('device_id')

    if not key or not hwid:
        return jsonify({"status": 1, "msg": "Missing Parameters"})

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT hwid, expiry_timestamp FROM keys_table WHERE license_key = ?",
        (key,)
    )
    row = cursor.fetchone()

    if row:
        db_hwid, expiry = row
        now = int(time.time())

        if now >= expiry:
            conn.close()
            return jsonify({"status": 3, "msg": "Key Expired"})

        if not db_hwid:
            cursor.execute(
                "UPDATE keys_table SET hwid = ? WHERE license_key = ?",
                (hwid, key)
            )
            conn.commit()
            db_hwid = hwid

        if db_hwid != hwid:
            conn.close()
            return jsonify({"status": 2, "msg": "Key used on another device"})

        conn.close()
        return jsonify({
            "status": 0,
            "msg": "Login Success",
            "expiry": expiry
        })

    conn.close()
    return jsonify({"status": 4, "msg": "Invalid Key"})

# =========================
# START SERVER (RENDER FIX)
# =========================
if __name__ == "__main__":
    init_db()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
