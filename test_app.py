import os
import sqlite3
from fastapi.testclient import TestClient

# Setup database file
DB_FILE = "test_tracking.db"

try:
    import app
    # Override
    app.DB_FILE = DB_FILE
    client = TestClient(app.app)
except ImportError as e:
    print(f"Import error: {e}")
    exit(1)

def setup():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    app.init_db()

def teardown():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def run_tests():
    setup()
    try:
        print("Testing /open endpoint...")
        response = client.get("/open/test_email_123")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert response.headers["content-type"] == "image/png"
        
        # Verify db insert
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT email_id FROM opens WHERE email_id=?", ("test_email_123",))
        row = c.fetchone()
        conn.close()
        assert row is not None, "Open log not found in db"
        
        print("Testing /click endpoint...")
        response = client.get("/click", params={"id": "test_email_123", "url": "https://example.com"}, follow_redirects=False)
        assert response.status_code in [307, 302], f"Expected redirect, got {response.status_code}"
        assert response.headers["location"] == "https://example.com"
        
        # Verify db insert
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT url FROM clicks WHERE email_id=?", ("test_email_123",))
        row = c.fetchone()
        conn.close()
        assert row is not None, "Click log not found in db"
        
        print("Testing /dashboard endpoint...")
        response = client.get("/dashboard")
        assert response.status_code == 200
        assert "test_email_123" in response.text
        
        print("All tests passed successfully!")
    finally:
        teardown()

if __name__ == "__main__":
    run_tests()
