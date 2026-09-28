from fastapi import FastAPI
import socket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.database import engine, Base, SessionLocal
from sqlalchemy import text
from app.routes import receipt_routes, split_routes, user_routes, auth_routes
from app import models

Base.metadata.create_all(bind=engine)

def migrate_db_columns():
    """Ensure newly added columns exist in sqlite."""
    with engine.connect() as conn:
        try:
            res = conn.execute(text("PRAGMA table_info(users)")).fetchall()
            cols = [row[1] for row in res]
            if "username" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100)"))
            if "password_hash" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
            if "created_at" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN created_at DATETIME"))
            conn.commit()
        except Exception:
            pass

migrate_db_columns()

app = FastAPI(title="Gemini Receipt Splitter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def seed_users():
    db = SessionLocal()
    for user_id, name in [(1, "Alice"), (2, "Bob"), (3, "Charlie")]:
        if not db.query(models.User).filter(models.User.id == user_id).first():
            db.add(models.User(id=user_id, name=name, email=f"user{user_id}@example.com", username=name.lower()))
    db.commit()
    db.close()

seed_users()

app.include_router(auth_routes.router)
app.include_router(receipt_routes.router)
app.include_router(split_routes.router)
app.include_router(user_routes.router)

@app.get("/")
def serve_frontend():
    return FileResponse("index.html")

@app.get("/manifest.json")
def serve_manifest():
    return FileResponse("manifest.json")

@app.get("/sw.js")
def serve_sw():
    return FileResponse("sw.js", media_type="application/javascript")

@app.get("/network-ip")
def get_network_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return {"ip": ip}
    except Exception:
        return {"ip": "127.0.0.1"}