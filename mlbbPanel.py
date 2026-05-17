from flask import Flask, request, jsonify, render_template_string
import os  # Idinagdag para sa os.environ
from threading import Thread  # Idinagdag para sa Thread
import sqlite3
import time
import random
import string
import requests

# ===== WEBKEEP ALIVE =====
app_web = Flask(__name__)  # FIXED: pinalitan ng __name__
OWNER_ID = 8073609514

@app_web.route("/")
def home():
    return "Bot is online!"

def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    Thread(target=lambda: app_web.run(host="0.0.0.0", port=port, use_reloader=False)).start()

# Kung may isa ka pang Flask app instance para sa checker/verify, siguraduhing iba ang pangalan
app = Flask(__name__)  
DB_FILE = "slider_vip.db"

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

# ==========================================
# 🌐 HTML ADMIN PANEL
# ==========================================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Slider Mods - VIP Panel</title>
<style>
body{background:#121212;color:#e0e0e0;font-family:Arial;padding:20px;}
.container{max-width:1000px;margin:auto;}
.card{background:#1e1e1e;padding:20px;border-radius:10px;margin-bottom:20px;border:1px solid #333;}
h1,h2{color:#ff3b30;}
input,select,button{padding:12px;border-radius:5px;border:1px solid #444;font-size:15px;margin-bottom:10px;}
input,select{background:#2a2a2a;color:white;}
button{background:#ff3b30;color:white;border:none;cursor:pointer;}
table{width:100%;border-collapse:collapse;margin-top:15px;}
th,td{border:1px solid #333;padding:12px;text-align:left;}
th{background:#2a2a2a;color:#ff3b30;}
tr:nth-child(even){background:#161616;}
.badge-active{color:#34c759;font-weight:bold;}
.badge-expired{color:#ff3b30;font-weight:bold;}
.btn-reset{background:#ffcc00;color:black;padding:5px 10px;}
.btn-delete{background:#8e8e93;color:white;padding:5px 10px;}
</style>
</head>
<body>
<div class="container">
<h1>🤖 Slider Mods VIP Dashboard</h1>
<div class="card">
<h2>🔑 Generate Key</h2>
<form action="/admin/generate" method="POST">
<select name="time_type">
<option value="minutes">Minutes</option>
<option value="hours">Hours</option>
<option value="days" selected>Days</option>
</select>
<input type="number" name="duration" placeholder="Enter Time" required>
<button type="submit">Create Key</button>
</form>
<br>
<small>Examples:<br>3 + Minutes = 3 Minutes Key<br>2 + Hours = 2 Hours Key<br>7 + Days = 7 Days Key</small>
</div>
<div class="card">
<h2>🗄️ Database Keys</h2>
<table>
<thead>
<tr><th>License Key</th><th>HWID</th><th>Status</th><th>Actions</th></tr>
</thead>
<tbody>
{% for row in keys %}
<tr>
<td style="font-family:monospace;color:#ffe957;">{{ row[0] }}</td>
<td style="font-family:monospace;font-size:12px;color:#aaa;">
{% if row[1] %}{{ row[1] }}{% else %}Fresh (No Lock){% endif %}
</td>
<td>
{% if current_time >= row[2] %}
<span class="badge-expired">❌ Expired</span>
{% else %}
<span class="badge-active">✅ Active</span><br><small>{{ datetime_format(row[2]) }}</small>
{% endif %}
</td>
<td>
<a href="/admin/reset/{{ row[0] }}"><button class="btn-reset">Reset HWID</button></a>
<a href="/admin/delete/{{ row[0] }}"><button class="btn-delete">Delete</button></a>
</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>
</div>
</body>
</html>
"""

# ==========================================
# 🌐 DASHBOARD
# ==========================================
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

# ==========================================
# 🔑 GENERATE KEY
# ==========================================
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
    cursor.execute("INSERT INTO keys_table (license_key, hwid, expiry_timestamp) VALUES (?, '', ?)", (new_key, expiry_time))
    conn.commit()
    conn.close()

    return f'<script>alert("Generated Key:\\n\\n{new_key}");window.location.href="/";</script>'

# ==========================================
# 🔄 RESET HWID
# ==========================================
@app.route('/admin/reset/<string:key>', methods=['GET'])
def admin_reset_hwid(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE keys_table SET hwid = '' WHERE license_key = ?", (key,))
    conn.commit()
    conn.close()
    return f'<script>alert("HWID Reset Success\\n\\n{key}");window.location.href="/";</script>'

# ==========================================
# ❌ DELETE KEY
# ==========================================
@app.route('/admin/delete/<string:key>', methods=['GET'])
def admin_delete_key(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keys_table WHERE license_key = ?", (key,))
    conn.commit()
    conn.close()
    return f'<script>alert("Deleted Key\\n\\n{key}");window.location.href="/";</script>'

# ==========================================
# 📱 VERIFY API
# ==========================================
@app.route('/verify', methods=['POST'])
def verify_key():
    key = request.form.get('key')
    hwid = request.form.get('device_id')

    if not key or not hwid:
        return jsonify({"status":1,"msg":"Missing Parameters"})

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hwid, expiry_timestamp FROM keys_table WHERE license_key = ?", (key,))
    row = cursor.fetchone()

    if row:
        db_hwid, expiry = row
        current_time = int(time.time())

        if current_time >= expiry:
            conn.close()
            return jsonify({"status":3,"msg":"Key Expired"})

        if not db_hwid or db_hwid == "":
            cursor.execute("UPDATE keys_table SET hwid = ? WHERE license_key = ?", (hwid, key))
            conn.commit()
            db_hwid = hwid

        if db_hwid != hwid:
            conn.close()
            return jsonify({"status":2,"msg":"Key used on another device"})

        conn.close()
        return jsonify({"status":0,"msg":"Login Success","expiry":expiry})

    conn.close()
    return jsonify({"status":4,"msg":"Invalid Key"})

# ==========================================
# 🚀 START SERVER
# ==========================================
if __name__ == "__main__":  # FIXED: Nilagyan ng tamang underscores
    init_db()  # Inuna natin ang pag-init ng db bago mag-start ang app
    keep_alive()

    print("\n======================================")
    print("🚀 SLIDER MODS SERVER ONLINE")
    print("📱 API: https://slidermods.duckdns.org/verify")
    print("🌐 PANEL: https://slidermods.duckdns.org/")
    print("======================================\n")
    
    # Sa Render, dapat basahin ang port galing sa environment variable kung ito ang pangunahing app
    port_env = int(os.environ.get("PORT", 8274))
    app.run(host='0.0.0.0', port=port_env)
