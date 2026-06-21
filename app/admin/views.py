from typing import Any

from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from markupsafe import Markup
from sqladmin import ModelView, action
from sqlalchemy import select
from starlette.requests import Request

from app.admin.context import current_request
from app.database import AsyncSessionLocal
from app.models import AuditLog, DeletionRequest, User


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

    async def on_model_delete(self, model: Any, request: Request) -> None:
        role = request.session.get("role", "unknown")
        if role != "admin":
            raise HTTPException(
                status_code=403,
                detail="Только администратор может удалять записи напрямую.",
            )

        # Прямое удаление админом (перехватываем перед удалением)
        async with AsyncSessionLocal() as session:
            log = AuditLog(
                actor_role=role,
                action_type="DELETE",
                entity_name="User",
                details=f"Прямое удаление пользователя: {model.username} ({model.email})",
            )
            session.add(log)
            await session.commit()

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

                    # Запрос на удаление
                    user = await session.get(User, int(pk))
                    user_info = (
                        f"{user.username} ({user.email})" if user else f"ID {pk}"
                    )

                    log = AuditLog(
                        actor_role=role,
                        action_type="REQUEST_DELETE",
                        entity_name="DeletionRequest",
                        details=f"Создана заявка на удаление пользователя: {user_info}",
                    )
                    session.add(log)
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
        role = request.session.get("role", "unknown")
        async with AsyncSessionLocal() as session:
            for pk in pks:
                if not pk:
                    continue
                req = await session.get(DeletionRequest, int(pk))
                if req and req.status == "pending":
                    user = await session.get(User, req.user_id)
                    user_info = (
                        f"{user.username} ({user.email})"
                        if user
                        else f"User ID {req.user_id}"
                    )

                    # Одобрение
                    log = AuditLog(
                        actor_role=role,
                        action_type="APPROVE",
                        entity_name="DeletionRequest",
                        details=f"Одобрено удаление пользователя: {user_info}",
                    )
                    session.add(log)

                    if user:
                        await session.delete(user)
            await session.commit()

        url = request.url_for("admin:list", identity=self.identity)
        return RedirectResponse(url)

    @action(name="reject", label="Отклонить", add_in_detail=True, add_in_list=True)
    async def reject_request(self, request: Request):
        pks = request.query_params.get("pks", "").split(",")
        role = request.session.get("role", "unknown")
        async with AsyncSessionLocal() as session:
            for pk in pks:
                if not pk:
                    continue
                req = await session.get(DeletionRequest, int(pk))
                if req and req.status == "pending":
                    # Отклонение
                    log = AuditLog(
                        actor_role=role,
                        action_type="REJECT",
                        entity_name="DeletionRequest",
                        details=f"Отклонена заявка на удаление пользователя ID {req.user_id} (Запросил: {req.requested_by})",
                    )
                    session.add(log)
                    await session.delete(req)
            await session.commit()

        url = request.url_for("admin:list", identity=self.identity)
        return RedirectResponse(url)


class AuditLogAdmin(ModelView, model=AuditLog):
    name = "Журнал аудита"
    name_plural = "Журнал аудита"
    icon = "fa-solid fa-clipboard-list"

    column_list = [
        AuditLog.id,
        AuditLog.timestamp,
        AuditLog.actor_role,
        AuditLog.action_type,
        AuditLog.entity_name,
        AuditLog.details,
    ]
    column_searchable_list = [AuditLog.action_type, AuditLog.details]
    column_sortable_list = [
        AuditLog.id,
        AuditLog.timestamp,
        AuditLog.actor_role,
        AuditLog.action_type,
    ]
    column_default_sort = ("timestamp", True)

    can_create = False
    can_edit = False
    can_delete = False

    def is_accessible(self, request: Request) -> bool:
        return request.session.get("role") == "admin"
