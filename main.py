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

def sync_postgres_sequences():
    """Ensure PostgreSQL sequences are synced with MAX(id) if rows were manually inserted."""
    try:
        with engine.connect() as conn:
            if not engine.url.drivername.startswith("sqlite"):
                for table in ["users", "receipts", "items", "item_shares"]:
                    conn.execute(text(f"""
                        SELECT setval(
                            pg_get_serial_sequence('{table}', 'id'),
                            COALESCE((SELECT MAX(id) FROM {table}), 1),
                            (SELECT MAX(id) IS NOT NULL FROM {table})
                        );
                    """))
                conn.commit()
    except Exception:
        pass

def seed_users():
    db = SessionLocal()
    try:
        for name in ["Alice", "Bob", "Charlie"]:
            uname = name.lower()
            if not db.query(models.User).filter(models.User.username == uname).first():
                db.add(models.User(name=name, email=f"{uname}@example.com", username=uname))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

seed_users()
sync_postgres_sequences()

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