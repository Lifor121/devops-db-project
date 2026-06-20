import io

import pandas as pd
from fastapi import UploadFile
from sqladmin import BaseView, ModelView, expose
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from app.database import AsyncSessionLocal
from app.models import User


class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")

        # В продакшене тут должен быть запрос к БД и сверка хэшей
        # Но пока что оставим захардкоженные данные
        if username == "admin" and password == "admin":
            # Записываем токен в сессию
            request.session.update({"token": "admin_session_token"})
            return True
        return False

    async def logout(self, request: Request) -> bool:
        # Очищаем сессию при выходе
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        # Этот метод вызывается при каждом переходе по страницам админки
        token = request.session.get("token")
        if not token:
            return False
        return True


authentication_backend = AdminAuth(secret_key="super_secret_key_for_session")


class UserAdmin(ModelView, model=User):
    # Колонки, которые отображаются в таблице
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
                    # Читаем файл в зависимости от расширения
                    if file.filename.endswith(".csv"):
                        df = pd.read_csv(io.BytesIO(contents))
                    elif file.filename.endswith(".xlsx"):
                        df = pd.read_excel(io.BytesIO(contents))
                    else:
                        message = "Неподдерживаемый формат. Используйте .csv или .xlsx"
                        return await self.templates.TemplateResponse(
                            request,
                            "import.html",
                            context={"message": message},
                        )

                    # Открываем сессию базы данных и построчно сохраняем записи
                    async with AsyncSessionLocal() as session:
                        added_count = 0
                        for _, row in df.iterrows():
                            # Извлекаем данные (учитываем, что возраст может быть пустым — NaN)
                            user = User(
                                username=str(row["username"]),
                                email=str(row["email"]),
                                full_name=str(row["full_name"])
                                if "full_name" in row and pd.notna(row["full_name"])
                                else None,
                                age=int(row["age"])
                                if "age" in row and pd.notna(row["age"])
                                else None,
                            )
                            session.add(user)
                            try:
                                await session.commit()
                                added_count += 1
                            except IntegrityError:
                                # Если пользователь с таким username или email уже есть — пропускаем
                                await session.rollback()

                        message = f"Обработка завершена. Успешно добавлено новых пользователей: {added_count}."
                except Exception as e:
                    message = f"Произошла ошибка при обработке файла: {str(e)}"

        return await self.templates.TemplateResponse(
            request, "import.html", context={"message": message}
        )
