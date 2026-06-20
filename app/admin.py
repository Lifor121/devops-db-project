import io
import json
import os
from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import UploadFile
from fastapi.responses import RedirectResponse
from sqladmin import BaseView, ModelView, action, expose
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from app.backup import create_backup
from app.database import AsyncSessionLocal
from app.models import DeletionRequest, User


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form["username"], form["password"]

        # Роль Администратора
        if username == "admin" and password == "admin":
            request.session.update({"token": "admin_token", "role": "admin"})
            return True
        # Роль Менеджера
        elif username == "manager" and password == "manager":
            request.session.update({"token": "manager_token", "role": "manager"})
            return True

        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "token" in request.session


authentication_backend = AdminAuth(secret_key="super_secret_key_for_session")


class UserAdmin(ModelView, model=User):
    column_list = [
        User.id,
        User.username,
        User.email,
        User.full_name,
        User.age,
        User.created_at,
    ]
    column_searchable_list = [User.username, User.email]
    column_sortable_list = [
        User.id,
        User.username,
        User.email,
        User.full_name,
        User.age,
        User.created_at,
    ]

    # Отключаем стандартное удаление
    can_delete = False

    # Создаем кнопку для выделенных пользователей
    @action(
        name="request_deletion",
        label="Запросить удаление",
        confirmation_message="Отправить администратору запрос на удаление выделенных пользователей?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def request_deletion(self, request: Request):
        # Достаем ID из параметров URL и разбиваем по запятой
        pks = request.query_params.get("pks", "").split(",")
        role = request.session.get("role", "unknown")

        async with AsyncSessionLocal() as session:
            for pk in pks:
                if not pk:  # Защита от пустых строк
                    continue

                stmt = select(DeletionRequest).where(
                    DeletionRequest.user_id == int(pk),
                    DeletionRequest.status == "pending",
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()

                if not existing:
                    new_req = DeletionRequest(user_id=int(pk), requested_by=role)
                    session.add(new_req)
            await session.commit()

        url = request.url_for("admin:list", identity=self.identity)
        return RedirectResponse(url)

    # Настройки отображения в меню
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"


class ImportView(BaseView):
    name = "Import Data"
    icon = "fa-solid fa-file-import"

    @expose("/import", methods=["GET", "POST"])
    async def import_data(self, request):
        message = ""
        if request.method == "POST":
            form = await request.form()
            file: UploadFile = form.get("file")

            if file and file.filename:
                contents = await file.read()
                try:
                    # Читаем файл
                    if file.filename.endswith(".csv"):
                        df = pd.read_csv(io.BytesIO(contents))
                    elif file.filename.endswith(".xlsx"):
                        df = pd.read_excel(io.BytesIO(contents))
                    else:
                        message = "Неподдерживаемый формат. Используйте .csv или .xlsx"
                        return await self.templates.TemplateResponse(
                            request,
                            "import.html",
                            context={"request": request, "message": message},
                        )

                    df = df.where(pd.notnull(df), None)

                    async with AsyncSessionLocal() as session:
                        added_count = 0
                        error_log = []

                        for i, (_, row) in enumerate(df.iterrows()):
                            try:
                                # Безопасно достаем значения
                                fname_val = row.get("full_name")
                                age_val = row.get("age")

                                user = User(
                                    username=str(row["username"]),
                                    email=str(row["email"]),
                                    full_name=str(fname_val)
                                    if fname_val is not None
                                    else None,
                                    age=int(age_val) if age_val is not None else None,
                                )
                                session.add(user)
                                await session.commit()
                                added_count += 1

                            except ValueError as ve:
                                await session.rollback()
                                error_log.append(
                                    f"Строка {i + 2} ({row.get('username')}): {str(ve)}"
                                )

                            except IntegrityError:
                                await session.rollback()

                        message = (
                            f"Обработка завершена. Успешно добавлено: {added_count}."
                        )
                        if error_log:
                            message += " Ошибки: " + " | ".join(error_log)

                except Exception as e:
                    message = f"Произошла ошибка при обработке файла: {str(e)}"

        return await self.templates.TemplateResponse(
            request, "import.html", context={"request": request, "message": message}
        )


class RestoreView(BaseView):
    name = "System Restore"
    icon = "fa-solid fa-truck-medical"

    @expose("/restore", methods=["GET", "POST"])
    async def restore_data(self, request):
        message = ""
        backup_path = "backups/users_backup.json"

        # Обработка нажатий кнопок в интерфейсе
        if request.method == "POST":
            form = await request.form()
            action = form.get("action")

            if action == "create_backup":
                success = await create_backup()
                if success:
                    message = "Резервная копия успешно создана/обновлена."
                else:
                    message = "Отмена: невозможно создать бэкап, так как таблица пользователей пуста."
            elif action == "restore_backup":
                if not os.path.exists(backup_path):
                    message = "Ошибка: Файл бэкапа не найден!"
                else:
                    try:
                        with open(backup_path, "r", encoding="utf-8") as f:
                            data = json.load(f)

                        async with AsyncSessionLocal() as session:
                            # Получаем все существующие username и email из БД
                            existing = await session.execute(
                                select(User.username, User.email)
                            )
                            existing_rows = existing.all()

                            # Превращаем их в множества
                            existing_usernames = {row.username for row in existing_rows}
                            existing_emails = {row.email for row in existing_rows}

                            added_count = 0
                            skipped_count = 0

                            # Перебираем бэкап и добавляем только недостающие записи
                            for item in data:
                                # Если такой пользователь уже есть - пропускаем
                                if (
                                    item["username"] in existing_usernames
                                    or item["email"] in existing_emails
                                ):
                                    skipped_count += 1
                                    continue

                                user = User(
                                    username=item["username"],
                                    email=item["email"],
                                    full_name=item.get("full_name"),
                                    age=item.get("age"),
                                )
                                if item.get("created_at"):
                                    user.created_at = datetime.fromisoformat(
                                        item["created_at"]
                                    )

                                session.add(user)
                                added_count += 1

                            # 3. Сохраняем только новых пользователей
                            await session.commit()

                        message = f"Успех! Слияние завершено. Восстановлено записей: {added_count}. Пропущено дубликатов: {skipped_count}."
                    except Exception as e:
                        message = f"Произошла ошибка при чтении бэкапа: {str(e)}"

        # Проверка доступности файла
        backup_exists = os.path.exists(backup_path)
        backup_time = None
        backup_records_count = 0
        backup_valid = False

        if backup_exists:
            try:
                mtime = os.path.getmtime(backup_path)
                backup_time = datetime.fromtimestamp(mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                # Читаем файл, чтобы проверить целостность
                with open(backup_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    backup_records_count = len(data)
                    backup_valid = True
            except Exception:
                # Если JSON сломан, помечаем бэкап как невалидный
                backup_valid = False

        # Проверяем состояние БД
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(func.count(User.id)))
            count = result.scalar()
            db_empty = count == 0

        context = {
            "request": request,
            "message": message,
            "db_empty": db_empty,
            "backup_exists": backup_exists,
            "backup_valid": backup_valid,
            "backup_time": backup_time,
            "backup_records_count": backup_records_count,
        }
        return await self.templates.TemplateResponse(
            request, "restore.html", context=context
        )


class DeletionRequestAdmin(ModelView, model=DeletionRequest):
    name = "Запросы на удаление"
    name_plural = "Запросы на удаление"
    icon = "fa-solid fa-envelope-open-text"

    column_list = [
        DeletionRequest.id,
        DeletionRequest.user_id,
        DeletionRequest.requested_by,
        DeletionRequest.status,
        DeletionRequest.created_at,
    ]

    # Запрещаем ручное редактирование логов
    can_create = False
    can_edit = False
    can_delete = False

    # ДОСТУП: Видно только администратору
    def is_accessible(self, request: Request) -> bool:
        return request.session.get("role") == "admin"

    @action(
        name="approve",
        label="Одобрить (Удалить из БД)",
        confirmation_message="Внимание: Пользователи будут удалены безвозвратно!",
        add_in_detail=True,
        add_in_list=True,
    )
    async def approve_request(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        async with AsyncSessionLocal() as session:
            for pk in pks:
                if not pk:
                    continue
                req = await session.get(DeletionRequest, int(pk))
                if req and req.status == "pending":
                    req.status = "approved"
                    user = await session.get(User, req.user_id)
                    if user:
                        await session.delete(user)
            await session.commit()

        url = request.url_for("admin:list", identity=self.identity)
        return RedirectResponse(url)

    @action(name="reject", label="Отклонить", add_in_detail=True, add_in_list=True)
    async def reject_request(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        async with AsyncSessionLocal() as session:
            for pk in pks:
                if not pk:
                    continue
                req = await session.get(DeletionRequest, int(pk))
                if req and req.status == "pending":
                    await session.delete(req)
            await session.commit()

        url = request.url_for("admin:list", identity=self.identity)
        return RedirectResponse(url)
