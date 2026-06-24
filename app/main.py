from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqladmin import Admin

from app.admin.auth import authentication_backend
from app.admin.custom import ImportView, RestoreView
from app.admin.views import AuditLogAdmin, DeletionRequestAdmin, UserAdmin
from app.backup import create_backup
from app.database import Base, engine

app = FastAPI(title="User Service", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")

DB_OFFLINE_HTML = Path("templates/503.html").read_text(encoding="utf-8")


@app.middleware("http")
async def global_ui_injector_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        return HTMLResponse(content=DB_OFFLINE_HTML, status_code=503)

    # Перехватываем GET-запрос к корню админки
    if request.url.path == "/admin/" and request.method == "GET":
        # Если sqladmin пытается отрендерить дашборд (200) или падает (500)
        # Это значит, что пользователь АВТОРИЗОВАН (иначе был бы 302 на логин)
        if response.status_code in [200, 500]:
            # Моментально перекидываем в список пользователей
            return RedirectResponse(url="/admin/user/list", status_code=303)

    # Ловим стандартную 500-ю ошибку админки и подменяем на нашу
    if response.status_code >= 500:
        return HTMLResponse(content=DB_OFFLINE_HTML, status_code=503)

    # Если всё хорошо (200 OK) — впрыскиваем переводы и стили
    if response.status_code == 200 and "text/html" in response.headers.get(
        "content-type", ""
    ):
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        html = body.decode("utf-8")

        try:
            role = request.session.get("role", "unknown")
        except Exception:
            role = "unknown"

        injection = '<script src="/static/js/translations.js"></script>'
        if role == "manager":
            injection += '<link rel="stylesheet" href="/static/css/manager.css">'
        elif role == "admin":
            injection += '<link rel="stylesheet" href="/static/css/admin.css">'

        html = html.replace("</head>", f"{injection}</head>")

        new_response = HTMLResponse(content=html, status_code=200)
        for k, v in response.headers.items():
            if k.lower() not in ["content-length", "content-type"]:
                new_response.headers[k] = v
        return new_response

    return response


# Инициализация админки
admin = Admin(
    app,
    engine,
    authentication_backend=authentication_backend,
    templates_dir="templates",
    title="Панель управления",
)
admin.add_view(UserAdmin)
admin.add_view(ImportView)
admin.add_view(RestoreView)
admin.add_view(DeletionRequestAdmin)
admin.add_view(AuditLogAdmin)


@app.on_event("startup")
async def startup():
    # Делаем бэкап при старте
    await create_backup()

    # Запускаем планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(create_backup, "interval", hours=12)
    scheduler.start()


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/admin")


@app.get("/health")
async def health_check():
    return {"status": "ok"}
