from sqladmin import ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

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
