from typing import Any

from fastapi.responses import RedirectResponse
from sqladmin import ModelView, action
from sqlalchemy import select
from starlette.requests import Request

from app.database import AsyncSessionLocal
from app.models import DeletionRequest, User


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

    can_delete = False

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

    # Настройки отображения в меню
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"


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
