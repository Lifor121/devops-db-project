import re
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, validates
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    @validates("email")
    def validate_email(self, key, address):
        # Проверяем наличие @ и точки, и отсутствие пробелов
        if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", address):
            raise ValueError(f"Некорректный формат email адреса: {address}")
        return address.lower()  # Заодно приводим к нижнему регистру

    @validates("age")
    def validate_age(self, key, age):
        if age is not None:
            age = int(age)  # Пытаемся привести к числу
            if age < 0 or age > 120:
                raise ValueError(
                    f"Возраст должен быть от 0 до 120 лет, передано: {age}"
                )
        return age

    @validates("full_name")
    def validate_full_name(self, key, name):
        if name:
            name = str(name).strip()
            if len(name) < 2:
                raise ValueError("Имя слишком короткое (минимум 2 символа)")
            # Разрешаем только буквы, пробелы и дефисы (без цифр и спецсимволов)
            if not re.match(r"^[A-Za-zА-Яа-яЁё\s\-]+$", name):
                raise ValueError(f"Имя должно содержать только буквы: {name}")
        return name
