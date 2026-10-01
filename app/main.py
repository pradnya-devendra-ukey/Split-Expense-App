from fastapi import FastAPI
import socket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.database import engine, Base, SessionLocal
from sqlalchemy import text
from app.routes import receipt_routes, split_routes, user_routes, auth_routes, group_routes
from app import models

# 1. Create any missing tables
Base.metadata.create_all(bind=engine)

def migrate_db_columns():
    """Ensure newly added columns exist in both SQLite and PostgreSQL."""
    try:
        with engine.connect() as conn:
            if engine.url.drivername.startswith("sqlite"):
                # SQLite migrations
                res = conn.execute(text("PRAGMA table_info(users)")).fetchall()
                cols = [row[1] for row in res]
                if "username" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(100)"))
                if "password_hash" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
                if "upi_id" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN upi_id VARCHAR(100)"))
                if "phone" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(50)"))
                if "default_currency" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN default_currency VARCHAR(10) DEFAULT 'INR'"))
                if "created_at" not in cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN created_at DATETIME"))

                res_r = conn.execute(text("PRAGMA table_info(receipts)")).fetchall()
                cols_r = [row[1] for row in res_r]
                if "join_code" not in cols_r:
                    conn.execute(text("ALTER TABLE receipts ADD COLUMN join_code VARCHAR(10)"))
                if "tax_amount" not in cols_r:
                    conn.execute(text("ALTER TABLE receipts ADD COLUMN tax_amount NUMERIC(10,2) DEFAULT 0.0"))
                if "tip_amount" not in cols_r:
                    conn.execute(text("ALTER TABLE receipts ADD COLUMN tip_amount NUMERIC(10,2) DEFAULT 0.0"))
                if "tax_split_method" not in cols_r:
                    conn.execute(text("ALTER TABLE receipts ADD COLUMN tax_split_method VARCHAR(20) DEFAULT 'proportional'"))
                if "currency" not in cols_r:
                    conn.execute(text("ALTER TABLE receipts ADD COLUMN currency VARCHAR(10) DEFAULT 'INR'"))
                if "currency_symbol" not in cols_r:
                    conn.execute(text("ALTER TABLE receipts ADD COLUMN currency_symbol VARCHAR(5) DEFAULT '₹'"))
                if "group_id" not in cols_r:
                    conn.execute(text("ALTER TABLE receipts ADD COLUMN group_id INTEGER"))

                res_s = conn.execute(text("PRAGMA table_info(receipt_settlements)")).fetchall()
                cols_s = [row[1] for row in res_s]
                if "payee_id" not in cols_s:
                    conn.execute(text("ALTER TABLE receipt_settlements ADD COLUMN payee_id INTEGER"))
                
                conn.commit()
            else:
                # PostgreSQL migrations using ADD COLUMN IF NOT EXISTS
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100);"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS upi_id VARCHAR(100);"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS phone VARCHAR(50);"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS default_currency VARCHAR(10) DEFAULT 'INR';"))
                conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;"))

                conn.execute(text("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS join_code VARCHAR(10);"))
                conn.execute(text("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS tax_amount NUMERIC(10,2) DEFAULT 0.0;"))
                conn.execute(text("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS tip_amount NUMERIC(10,2) DEFAULT 0.0;"))
                conn.execute(text("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS tax_split_method VARCHAR(20) DEFAULT 'proportional';"))
                conn.execute(text("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS currency VARCHAR(10) DEFAULT 'INR';"))
                conn.execute(text("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS currency_symbol VARCHAR(5) DEFAULT '₹';"))
                conn.execute(text("ALTER TABLE receipts ADD COLUMN IF NOT EXISTS group_id INTEGER;"))

                conn.execute(text("ALTER TABLE receipt_settlements ADD COLUMN IF NOT EXISTS payee_id INTEGER;"))

                conn.commit()
    except Exception as e:
        print(f"Migration notice: {e}")

migrate_db_columns()

app = FastAPI(title="SmartSplit - AI Expense Splitter API")

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
                for table in ["users", "receipts", "items", "item_shares", "receipt_settlements", "receipt_payers", "groups", "group_members"]:
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
        for name in ["Alice", "Bob", "Charlie", "David", "Emma"]:
            uname = name.lower()
            if not db.query(models.User).filter(models.User.username == uname).first():
                db.add(models.User(name=name, email=f"{uname}@example.com", username=uname, default_currency="INR"))
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
app.include_router(group_routes.router)

@app.get("/")
def serve_frontend():
    return FileResponse(
        "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"}
    )

@app.get("/manifest.json")
def serve_manifest():
    return FileResponse("manifest.json")

@app.get("/sw.js")
def serve_sw():
    return FileResponse(
        "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )

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