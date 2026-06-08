from sqladmin import ModelView
from app.models import User

class UserAdmin(ModelView, model=User):
    # Колонки, которые отображаются в таблице
    column_list = [
        User.id,
        User.username,
        User.email,
        User.full_name,
        User.age,
        User.created_at
    ]

    column_searchable_list = [User.username, User.email]
    column_sortable_list = [User.id, User.created_at]

    # Настройки отображения в меню
    name = "User"
    name_plural = "Users"
    icon = "fa-solid fa-user"
