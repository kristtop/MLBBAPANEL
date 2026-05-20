from flask import Flask, request, jsonify, render_template_string, redirect, session
import os
import psycopg2
import time
import random
import string
import uuid
from psycopg2.errors import UniqueViolation

app = Flask(__name__)
app.secret_key = "slider_super_secret_key"
ADMIN_PASSWORD = "qwerty12213"

# =========================
# DATABASE
# =========================
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Gumawa ng table kung wala pa
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keys_table (
            license_key TEXT PRIMARY KEY,
            hwid TEXT,
            expiry_timestamp INTEGER
        )
    ''')
    conn.commit()

    # MAGIC MIGRATION: Idadagdag ang 'game' column kung luma ang table para hindi mag-crash
    try:
        cursor.execute("ALTER TABLE keys_table ADD COLUMN game TEXT DEFAULT 'MLBB';")
        conn.commit()
    except Exception:
        conn.rollback() # Laktawan kung may column na
        
    conn.close()

# =========================
# HTML PANEL (UPDATED UI WITH MULTI-GAME GENERATOR)
# =========================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Slider Mods - VIP Panel</title>

<style>
body{
    background:#121212;
    color:#e0e0e0;
    font-family:Arial;
    padding:20px;
}
.container{max-width:1000px;margin:auto;}
.card{
    background:#1e1e1e;
    padding:20px;
    border-radius:10px;
    margin-bottom:20px;
    border:1px solid #333;
}
h1,h2{color:#ff3b30;}

input,select,button{
    padding:12px;
    border-radius:5px;
    border:1px solid #444;
    font-size:15px;
    margin-bottom:10px;
}
input,select{background:#2a2a2a;color:white;}
button{
    background:#ff3b30;
    color:white;
    border:none;
    cursor:pointer;
}
table{
    width:100%;
    border-collapse:collapse;
    margin-top:15px;
}
th,td{
    border:1px solid #333;
    padding:12px;
    text-align:left;
}
th{
    background:#2a2a2a;
    color:#ff3b30;
}
tr:nth-child(even){background:#161616;}
.badge-active{color:#34c759;font-weight:bold;}
.badge-expired{color:#ff3b30;font-weight:bold;}
.badge-nolock{color:#0a84ff;font-weight:bold;}
.badge-mlbb{background:#007aff;color:white;padding:2px 6px;border-radius:3px;font-size:11px;}
.badge-codm{background:#ff9500;color:black;padding:2px 6px;border-radius:3px;font-size:11px;font-weight:bold;}
.btn-reset{background:#ffcc00;color:black;padding:5px 10px;}
.btn-nolock{background:#0a84ff;color:white;padding:5px 10px;}
.btn-delete{background:#8e8e93;color:white;padding:5px 10px;}
</style>
</head>

<body>

<div class="container">

<div style="display:flex;justify-content:space-between;align-items:center;">
<h1>🤖 Slider Mods VIP Dashboard</h1>
<a href="/logout"><button style="background:#ff3b30;color:white;">Logout</button></a>
</div>

<!-- MAIN GENERATOR -->
<div class="card">
<h2>🔑 Generate VIP Key</h2>

<form action="/admin/generate" method="POST">
<label>Target Game:</label>
<select name="game" style="border: 1px solid #ff3b30;">
    <option value="MLBB">Mobile Legends (MLBB)</option>
    <option value="CODM">Call of Duty Mobile (CODM)</option>
</select>

<br>
<label>Days</label>
<select name="days">
<option value="0">0 Day</option>
{% for i in range(1,31) %}
<option value="{{i}}">{{i}} Day</option>
{% endfor %}
</select>

<label>Hours</label>
<select name="hours">
<option value="0">0 Hour</option>
{% for i in range(1,25) %}
<option value="{{i}}">{{i}} Hour</option>
{% endfor %}
</select>

<label>Minutes</label>
<select name="minutes">
<option value="0">0 Minute</option>
{% for i in range(1,60) %}
<option value="{{i}}">{{i}} Minute</option>
{% endfor %}
</select>

<button type="submit">Generate Random Key</button>
</form>
</div>

<!-- CUSTOM GENERATOR -->
<div class="card">
<h2>✏️ Custom Key Generator</h2>
<form action="/admin/custom_generate" method="POST">
<input type="text" name="custom_key" placeholder="Enter Custom Key Name" required>
<select name="game">
    <option value="MLBB">Target: MLBB</option>
    <option value="CODM">Target: CODM</option>
</select>
<br>
<input type="number" name="days" placeholder="Days" value="0" style="width:80px;">
<input type="number" name="hours" placeholder="Hours" value="0" style="width:80px;">
<input type="number" name="minutes" placeholder="Minutes" value="0" style="width:80px;">
<button type="submit" style="background:#0a84ff;">Generate Custom Key</button>
</form>
</div>

<!-- DATABASE TABLES -->
<div class="card">
<h2>🗄️ Database Keys</h2>

<input
type="text"
id="searchInput"
placeholder="Search Key or Game..."
style="width:100%;padding:12px;margin-top:10px;margin-bottom:15px;background:#2a2a2a;color:white;border:1px solid #444;border-radius:5px;"
onkeyup="searchKeys()">

<table>
<thead>
<tr>
<th>License Key</th>
<th>Game</th>
<th>HWID / Status</th>
<th>Expiry Status</th>
<th>Actions</th>
</tr>
</thead>

<tbody>
{% for row in keys %}
<tr>
<td style="font-family:monospace;color:#ffe957;">{{ row[0] }}</td>
<td>
    {% if row[3] == 'CODM' %}
    <span class="badge-codm">CODM</span>
    {% else %}
    <span class="badge-mlbb">MLBB</span>
    {% endif %}
</td>
<td style="font-family:monospace;font-size:12px;color:#aaa;">
{% if row[1] == 'NO_LOCK' %}
<span class="badge-nolock">🔓 Multi-Device (No Lock)</span>
{% elif row[1] %}
{{ row[1] }}
{% else %}
<span style="color:#34c759;">Fresh (Logs first device)</span>
{% endif %}
</td>

<td>
{% if current_time >= row[2] %}
<span class="badge-expired">❌ Expired</span>
{% else %}
<span class="badge-active">✅ Active</span><br>
<small>{{ datetime_format(row[2]) }}</small>
{% endif %}
</td>

<td style="display:flex;gap:5px;flex-wrap:wrap;">
<button type="button" onclick="copyKey('{{ row[0] }}')" style="background:#34c759;color:white;padding:5px 10px;border:none;border-radius:5px;cursor:pointer;">Copy Key</button>
<a href="/admin/reset/{{ row[0] }}"><button class="btn-reset">Reset HWID</button></a>
<a href="/admin/nolock/{{ row[0] }}"><button class="btn-nolock">No Lock</button></a>
<a href="/admin/edit/{{ row[0] }}"><button style="background:#0a84ff;color:white;padding:5px 10px;">Edit Time</button></a>
<a href="/admin/delete/{{ row[0] }}"><button class="btn-delete">Delete</button></a>
</td>
</tr>
{% endfor %}
</tbody>
</table>
</div>

</div>

<script>
async function copyKey(key){
    try{
        await navigator.clipboard.writeText(key);
        alert("Copied Key:\\n\\n" + key);
    }catch(err){
        const tempInput = document.createElement("input");
        tempInput.value = key;
        document.body.appendChild(tempInput);
        tempInput.select();
        document.execCommand("copy");
        document.body.removeChild(tempInput);
        alert("Copied Key:\\n\\n" + key);
    }
}

function searchKeys(){
    let input = document.getElementById("searchInput");
    let filter = input.value.toUpperCase();
    let table = document.querySelector("table");
    let tr = table.getElementsByTagName("tr");
    for(let i = 1; i < tr.length; i++){
        let tdKey = tr[i].getElementsByTagName("td")[0];
        let tdGame = tr[i].getElementsByTagName("td")[1];
        if(tdKey || tdGame){
            let txtKey = tdKey.textContent || tdKey.innerText;
            let txtGame = tdGame.textContent || tdGame.innerText;
            if(txtKey.toUpperCase().indexOf(filter) > -1 || txtGame.toUpperCase().indexOf(filter) > -1){
                tr[i].style.display = "";
            }else{
                tr[i].style.display = "none";
            }
        }
    }
}
</script>

</body>
</html>
"""

# =========================
# ADMIN LOGIN
# =========================
LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<title>Admin Login</title>
<style>
body{background:#121212;color:white;font-family:Arial;display:flex;justify-content:center;align-items:center;height:100vh;}
.box{background:#1e1e1e;padding:30px;border-radius:10px;width:350px;border:1px solid #333;}
input,button{width:100%;padding:12px;margin-top:10px;border:none;border-radius:5px;}
input{background:#2a2a2a;color:white;}
button{background:#ff3b30;color:white;cursor:pointer;}
h2{text-align:center;color:#ff3b30;}
</style>
</head>
<body>
<div class="box">
<h2>🔐 Admin Login</h2>
<form method="POST">
<input type="password" name="password" placeholder="Enter Password" required>
<button type="submit">Login</button>
</form>
</div>
</body>
</html>
"""

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect('/')
        return '<script>alert("Wrong Password");window.location.href="/login";</script>'
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/', methods=['GET'])
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect('/login')
    conn = get_db_connection()
    cursor = conn.cursor()
    # Kasama na ang 'game' sa select query natin ngayon
    cursor.execute("SELECT license_key, hwid, expiry_timestamp, game FROM keys_table ORDER BY expiry_timestamp DESC")
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
# KEY GENERATORS (WITH GAME PROTECTION)
# =========================
@app.route('/admin/custom_generate', methods=['POST'])
def custom_generate():
    if not session.get("admin_logged_in"):
        return redirect('/login')

    custom_key = request.form.get('custom_key')
    game_target = request.form.get('game', 'MLBB') # Kinukuha ang piniling laro
    days = int(request.form.get('days', 0))
    hours = int(request.form.get('hours', 0))
    minutes = int(request.form.get('minutes', 0))

    if not custom_key:
        return '<script>alert("Enter Custom Key");window.location.href="/";</script>'

    if days == 0 and hours == 0 and minutes == 0:
        expiry_time = 4102444800
    else:
        expiry_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)
        expiry_time = int(time.time()) + expiry_seconds

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT license_key FROM keys_table WHERE license_key = %s", (custom_key,))
        if cursor.fetchone():
            conn.close()
            return '<script>alert("Key Already Exists");window.location.href="/";</script>'

        cursor.execute("INSERT INTO keys_table (license_key, hwid, expiry_timestamp, game) VALUES (%s, '', %s, %s)", (custom_key, expiry_time, game_target))
        conn.commit()
        conn.close()
        return f'<script>alert("Custom Key Generated for {game_target}\\n\\n{custom_key}");window.location.href="/";</script>'
    except Exception as e:
        conn.rollback()
        conn.close()
        return f'<script>alert("Error:\\n\\n{str(e)}");window.location.href="/";</script>'

@app.route('/admin/generate', methods=['POST'])
def admin_generate():
    if not session.get("admin_logged_in"):
        return redirect('/login')

    game_target = request.form.get('game', 'MLBB')
    days = int(request.form.get('days', 0))
    hours = int(request.form.get('hours', 0))
    minutes = int(request.form.get('minutes', 0))

    if days == 0 and hours == 0 and minutes == 0:
        return '<script>alert("Enter Time First");window.location.href="/";</script>'

    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=14))
    expiry_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)

    # Prefix naming structure base sa game target
    if game_target == 'CODM':
        base_prefix = f"CODM_{days}d" if days > 0 else (f"CODM_{hours}h" if hours > 0 else f"CODM_{minutes}m")
    else:
        base_prefix = f"Slider_{days}d" if days > 0 else (f"Slider_{hours}h" if hours > 0 else f"Slider_{minutes}m")

    new_key = base_prefix + "_" + random_str
    expiry_time = int(time.time()) + expiry_seconds

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO keys_table (license_key, hwid, expiry_timestamp, game) VALUES (%s, '', %s, %s)", (new_key, expiry_time, game_target))
    conn.commit()
    conn.close()

    return f'<script>alert("Generated {game_target} Key:\\n\\n{new_key}\\n\\nExpiry:\\n{days}D {hours}H {minutes}M");window.location.href="/";</script>'

# =========================
# RESET HWID / NO LOCK
# =========================
@app.route('/admin/reset/<string:key>', methods=['GET'])
def admin_reset_hwid(key):
    if not session.get("admin_logged_in"):
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE keys_table SET hwid = '' WHERE license_key = %s", (key,))
    conn.commit()
    conn.close()
    return f'<script>alert("HWID Reset Success\\n\\n{key}");window.location.href="/";</script>'

@app.route('/admin/nolock/<string:key>', methods=['GET'])
def admin_no_lock_hwid(key):
    if not session.get("admin_logged_in"):
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE keys_table SET hwid = 'NO_LOCK' WHERE license_key = %s", (key,))
    conn.commit()
    conn.close()
    return f'<script>alert("Key set to NO LOCK (Multi-Device Allowed)\\n\\n{key}");window.location.href="/";</script>'

# =========================
# EDIT / DELETE KEY
# =========================
@app.route('/admin/delete/<string:key>', methods=['GET'])
def admin_delete_key(key):
    if not session.get("admin_logged_in"):
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keys_table WHERE license_key = %s", (key,))
    conn.commit()
    conn.close()
    return f'<script>alert("Deleted Key\\n\\n{key}");window.location.href="/";</script>'

@app.route('/admin/edit/<string:key>', methods=['GET', 'POST'])
def admin_edit_time(key):
    if not session.get("admin_logged_in"):
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        days = int(request.form.get('days', 0))
        hours = int(request.form.get('hours', 0))
        minutes = int(request.form.get('minutes', 0))
        added_seconds = (days * 86400) + (hours * 3600) + (minutes * 60)

        cursor.execute("SELECT expiry_timestamp FROM keys_table WHERE license_key = %s", (key,))
        row = cursor.fetchone()

        if row:
            current_expiry = row[0]
            now = int(time.time())
            new_expiry = (now if current_expiry < now else current_expiry) + added_seconds
            cursor.execute("UPDATE keys_table SET expiry_timestamp = %s WHERE license_key = %s", (new_expiry, key))
            conn.commit()

        conn.close()
        return '<script>alert("Time Updated Successfully");window.location.href="/";</script>'

    conn.close()
    return f'''
    <!DOCTYPE html>
    <html>
    <head><title>Edit Time</title>
    <style>
    body{{background:#121212;color:white;font-family:Arial;padding:30px;}}
    .box{{max-width:400px;margin:auto;background:#1e1e1e;padding:20px;border-radius:10px;border:1px solid #333;}}
    input,button{{width:100%;padding:12px;margin-top:10px;border:none;border-radius:5px;}}
    input{{background:#2a2a2a;color:white;}}
    button{{background:#0a84ff;color:white;cursor:pointer;}}
    </style></head>
    <body><div class="box"><h2>Edit Time</h2><p>{key}</p>
    <form method="POST">
    <input type="number" name="days" placeholder="Days" value="0">
    <input type="number" name="hours" placeholder="Hours" value="0">
    <input type="number" name="minutes" placeholder="Minutes" value="0">
    <button type="submit">Add Time</button>
    </form></div></body></html>
    '''

# =========================
# VERIFY API (STRICT GAME ISOLATION LOGIC)
# =========================
@app.route('/verify', methods=['POST'])
def verify_key():
    key = request.form.get('key')
    hwid = request.form.get('device_id')
    client_game = request.form.get('game', 'MLBB') # Default sa MLBB kapag walang pinasa ang injector

    if not key or not hwid:
        return jsonify({"status": 1, "msg": "Missing Parameters"})

    conn = get_db_connection()
    cursor = conn.cursor()

    # Kukunin din natin kung anong laro naka-assign ang susi sa system (row[2] -> game)
    cursor.execute("SELECT hwid, expiry_timestamp, game FROM keys_table WHERE license_key = %s", (key,))
    row = cursor.fetchone()

    if row:
        db_hwid, expiry, db_game = row
        now = int(time.time())

        # --- VALIDATION: Check kung para sa maling laro ang key ---
        if db_game.upper() != client_game.upper():
            conn.close()
            return jsonify({
                "status": 4, 
                "msg": f"This key belongs to {db_game} only!"
            })

        # Check Expired
        if now >= expiry:
            conn.close()
            return jsonify({"status": 3, "msg": "Key Expired"})

        # --- NO LOCK BYPASS LOGIC ---
        if db_hwid == 'NO_LOCK':
            conn.close()
            return jsonify({
                "status": 0,
                "msg": f"Login Success ({db_game} - No Lock)",
                "expiry": expiry
            })

        # Kung fresh key, i-lock sa unang device na gagamit
        if not db_hwid:
            cursor.execute("UPDATE keys_table SET hwid = %s WHERE license_key = %s", (hwid, key))
            conn.commit()
            db_hwid = hwid

        # Kung may nakatali nang HWID at hindi tugma sa gamit ngayon
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
# START SERVER
# =========================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
