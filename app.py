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
    conn.commit()
    conn.close()

@app.on_event("startup")
def on_startup():
    init_db()

def log_open(email_id: str, ip_address: str, user_agent: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO opens (email_id, ip_address, user_agent)
        VALUES (?, ?, ?)
    ''', (email_id, ip_address, user_agent))
    conn.commit()
    conn.close()

def log_click(email_id: str, url: str, ip_address: str, user_agent: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        INSERT INTO clicks (email_id, url, ip_address, user_agent)
        VALUES (?, ?, ?, ?)
    ''', (email_id, url, ip_address, user_agent))
    conn.commit()
    conn.close()

@app.get("/open/{email_id}")
async def track_open(email_id: str, request: Request, background_tasks: BackgroundTasks):
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    background_tasks.add_task(log_open, email_id, ip_address, user_agent)
    return Response(content=TRANSPARENT_PIXEL, media_type="image/png")

@app.get("/click")
async def track_click(id: str, url: str, request: Request, background_tasks: BackgroundTasks):
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    background_tasks.add_task(log_click, id, url, ip_address, user_agent)
    return RedirectResponse(url=url)

@app.get("/api/stats")
async def api_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT email_id, COUNT(*) as count, MAX(timestamp) as last_open FROM opens GROUP BY email_id ORDER BY last_open DESC')
    opens = [{"email_id": row[0], "count": row[1], "last_open": row[2]} for row in c.fetchall()]
    
    c.execute('SELECT email_id, url, COUNT(*) as count, MAX(timestamp) as last_click FROM clicks GROUP BY email_id, url ORDER BY last_click DESC')
    clicks = [{"email_id": row[0], "url": row[1], "count": row[2], "last_click": row[3]} for row in c.fetchall()]
    conn.close()
    
    return {"opens": opens, "clicks": clicks}

@app.get("/dashboard")
async def dashboard():
    return FileResponse("static/index.html")
