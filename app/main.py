from fastapi import FastAPI
from sqladmin import Admin

from app.admin import ImportView, UserAdmin, authentication_backend
from app.database import Base, engine

app = FastAPI(title="User Service", version="1.0.0")

admin = Admin(
    app,
    engine,
    authentication_backend=authentication_backend,
    templates_dir="templates",
)
admin.add_view(UserAdmin)
admin.add_view(ImportView)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
