from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqladmin import Admin

from app.admin.auth import authentication_backend
from app.admin.custom import ImportView, RestoreView
from app.admin.views import DeletionRequestAdmin, UserAdmin
from app.backup import create_backup
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
admin.add_view(RestoreView)
admin.add_view(DeletionRequestAdmin)


@app.on_event("startup")
async def startup():
    # Создаем таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Делаем немедленный бэкап при старте сервера
    await create_backup()

    # Запускаем планировщик, который будет делать бэкап каждые 12 часов
    scheduler = AsyncIOScheduler()
    scheduler.add_job(create_backup, "interval", hours=12)
    scheduler.start()


@app.get("/health")
async def health_check():
    return {"status": "ok"}
