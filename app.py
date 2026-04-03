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
    c.execute('SELECT email_id, MAX(subject) as subject, MAX(recipient) as recipient, MAX(account) as account, COUNT(*) as count, MAX(timestamp) as last_open FROM opens GROUP BY email_id ORDER BY last_open DESC')
    opens = [{"email_id": row[0], "subject": row[1], "recipient": row[2], "account": row[3], "count": row[4], "last_open": row[5]} for row in c.fetchall()]
    
    c.execute('SELECT email_id, url, MAX(subject) as subject, MAX(recipient) as recipient, MAX(account) as account, COUNT(*) as count, MAX(timestamp) as last_click FROM clicks GROUP BY email_id, url ORDER BY last_click DESC')
    clicks = [{"email_id": row[0], "url": row[1], "subject": row[2], "recipient": row[3], "account": row[4], "count": row[5], "last_click": row[6]} for row in c.fetchall()]
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

@app.get("/dashboard")
async def dashboard():
    response = FileResponse("static/index.html")
    # Set a cookie valid for 1 year to ignore their own visits
    response.set_cookie(key="ignore_tracking", value="true", max_age=31536000)
    return response
