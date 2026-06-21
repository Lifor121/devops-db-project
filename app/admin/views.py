from typing import Any

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from markupsafe import Markup
from sqladmin import ModelView, action
from sqlalchemy import select
from starlette.requests import Request

from app.admin.context import current_request
from app.database import AsyncSessionLocal
from app.models import DeletionRequest, User


def role_ui_formatter(model, attribute):
    req = current_request.get()
    role = req.session.get("role") if req else "unknown"

    val = (
        getattr(model, attribute.name)
        if hasattr(attribute, "name")
        else getattr(model, str(attribute), "")
    )

    if role == "manager":
        # Скрываем корзины
        style = """<style>
            a[href*='/delete'],
            button[data-bs-target*='delete'],
            form[action*='/delete'],
            a:has(i.fa-trash) {
                display: none !important;
            }
        </style>"""
        return Markup(f"{val} {style}")

    elif role == "admin":
        # Скрываем кастомное действие для админа
        style = """<style>
            a[href*='request_deletion'] {
                display: none !important;
            }
        </style>"""
        return Markup(f"{val} {style}")

    return val


class UserAdmin(ModelView, model=User):
    identity = "user"
    name = "Пользователи"
    name_plural = "Пользователи"
    icon = "fa-solid fa-users"

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

    # Подключаем инъекцию стилей к колонке ID
    column_formatters = {User.id: role_ui_formatter}

    can_delete = True

    def is_accessible(self, request: Request) -> bool:
        return request.session.get("role") in ["admin", "manager"]

    # Бэкенд-защита
    async def on_model_delete(self, model: Any, request: Request) -> None:
        if request.session.get("role") != "admin":
            raise HTTPException(
                status_code=403,
                detail="Только администратор может удалять записи напрямую.",
            )

    @action(
        name="request_deletion",
        label="Запросить удаление",
        confirmation_message="Отправить администратору запрос на удаление выделенных пользователей?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def request_deletion(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        role = request.session.get("role", "unknown")

        async with AsyncSessionLocal() as session:
            for pk in pks:
                if not pk:
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


class DeletionRequestAdmin(ModelView, model=DeletionRequest):
    name = "Запросы на удаление"
    name_plural = "Запросы на удаление"
    icon = "fa-solid fa-envelope-open-text"

    column_list = [
        DeletionRequest.id,
        DeletionRequest.user,
        DeletionRequest.requested_by,
        DeletionRequest.status,
        DeletionRequest.created_at,
    ]

    can_create = False
    can_edit = False
    can_delete = False

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
