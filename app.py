import sqlite3
import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import Response, RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import base64

app = FastAPI(title="Email Tracker")

app.mount("/static", StaticFiles(directory="static"), name="static")

DB_FILE = "tracking.db"

# 1x1 transparent PNG pixel
TRANSPARENT_PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS opens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT,
            url TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        c.execute("ALTER TABLE opens ADD COLUMN subject TEXT DEFAULT 'Unknown'")
        c.execute("ALTER TABLE opens ADD COLUMN recipient TEXT DEFAULT 'Unknown'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE clicks ADD COLUMN subject TEXT DEFAULT 'Unknown'")
        c.execute("ALTER TABLE clicks ADD COLUMN recipient TEXT DEFAULT 'Unknown'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE opens ADD COLUMN account TEXT DEFAULT 'Unknown'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE clicks ADD COLUMN account TEXT DEFAULT 'Unknown'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

@app.on_event("startup")
def on_startup():
    init_db()

def log_open(email_id: str, ip_address: str, user_agent: str, subject: str = "Unknown", recipient: str = "Unknown", account: str = "Unknown"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO opens (email_id, ip_address, user_agent, subject, recipient, account)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (email_id, ip_address, user_agent, subject, recipient, account))
    conn.commit()
    conn.close()

def log_click(email_id: str, url: str, ip_address: str, user_agent: str, subject: str = "Unknown", recipient: str = "Unknown", account: str = "Unknown"):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO clicks (email_id, url, ip_address, user_agent, subject, recipient, account)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (email_id, url, ip_address, user_agent, subject, recipient, account))
    conn.commit()
    conn.close()

@app.get("/open/{email_id}")
async def track_open(email_id: str, request: Request, background_tasks: BackgroundTasks, subject: str = "Unknown", recipient: str = "Unknown", account: str = "Unknown"):
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    
    # Check if the user has the ignore_tracking cookie
    if request.cookies.get("ignore_tracking") == "true":
        return Response(content=TRANSPARENT_PIXEL, media_type="image/png", headers=headers)
        
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    background_tasks.add_task(log_open, email_id, ip_address, user_agent, subject, recipient, account)
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    return Response(content=TRANSPARENT_PIXEL, media_type="image/png", headers=headers)

@app.get("/click")
async def track_click(id: str, url: str, request: Request, background_tasks: BackgroundTasks, subject: str = "Unknown", recipient: str = "Unknown", account: str = "Unknown"):
    # Check if the user has the ignore_tracking cookie
    if request.cookies.get("ignore_tracking") == "true":
        return RedirectResponse(url=url)
        
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    background_tasks.add_task(log_click, id, url, ip_address, user_agent, subject, recipient, account)
    return RedirectResponse(url=url)

@app.get("/api/stats")
async def api_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Fetch all opens
    c.execute('SELECT id, email_id, ip_address, user_agent, timestamp, subject, recipient, account FROM opens ORDER BY timestamp DESC')
    all_opens = c.fetchall()
    
    opens_dict = {}
    for row in all_opens:
        row_id, email_id, ip_address, user_agent, timestamp, subject, recipient, account = row
        if email_id not in opens_dict:
            opens_dict[email_id] = {
                "email_id": email_id,
                "subject": subject,
                "recipient": recipient,
                "account": account,
                "count": 0,
                "last_open": timestamp,
                "events": []
            }
        opens_dict[email_id]["count"] += 1
        opens_dict[email_id]["events"].append({
            "id": row_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": timestamp
        })
    opens = list(opens_dict.values())
    
    # Fetch all clicks
    c.execute('SELECT id, email_id, url, ip_address, user_agent, timestamp, subject, recipient, account FROM clicks ORDER BY timestamp DESC')
    all_clicks = c.fetchall()
    
    clicks_dict = {}
    for row in all_clicks:
        row_id, email_id, url, ip_address, user_agent, timestamp, subject, recipient, account = row
        key = (email_id, url)
        if key not in clicks_dict:
            clicks_dict[key] = {
                "email_id": email_id,
                "url": url,
                "subject": subject,
                "recipient": recipient,
                "account": account,
                "count": 0,
                "last_click": timestamp,
                "events": []
            }
        clicks_dict[key]["count"] += 1
        clicks_dict[key]["events"].append({
            "id": row_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "timestamp": timestamp
        })
    clicks = list(clicks_dict.values())
    
    conn.close()
    
    return {"opens": opens, "clicks": clicks}

@app.delete("/api/track/opens/{email_id}")
async def delete_opens(email_id: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM opens WHERE email_id = ?", (email_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/track/clicks/{email_id}")
async def delete_clicks(email_id: str, request: Request):
    data = await request.json()
    url = data.get("url")
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM clicks WHERE email_id = ? AND url = ?", (email_id, url))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/track/open/{id}")
async def delete_single_open(id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM opens WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/api/track/click/{id}")
async def delete_single_click(id: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM clicks WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/dashboard")
async def dashboard():
    response = FileResponse("static/index.html")
    # Set a cookie valid for 1 year to ignore their own visits
    response.set_cookie(key="ignore_tracking", value="true", max_age=31536000)
    return response
