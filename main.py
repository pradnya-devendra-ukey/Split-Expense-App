from fastapi import FastAPI
import socket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.database import engine, Base, SessionLocal
from app.routes import receipt_routes, split_routes, user_routes
from app import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gemini Receipt Splitter API")

def seed_users():
    db = SessionLocal()
    for user_id, name in [(1, "Alice"), (2, "Bob"), (3, "Charlie")]:
        if not db.query(models.User).filter(models.User.id == user_id).first():
            db.add(models.User(id=user_id, name=name, email=f"user{user_id}@example.com"))
    db.commit()
    db.close()

seed_users()

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