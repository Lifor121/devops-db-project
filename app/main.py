from fastapi import FastAPI
from sqladmin import Admin

from app.database import Base, engine
from app.admin import UserAdmin, authentication_backend

app = FastAPI(title="User Service", version="1.0.0")

admin = Admin(app, engine, authentication_backend=authentication_backend)
admin.add_view(UserAdmin)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
