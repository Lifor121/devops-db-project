import re
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
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

    @validates("username")
    def validate_username(self, key, username):
        if username:
            return str(username).strip()
        return username

    @validates("email")
    def validate_email(self, key, address):
        if address:
            # Убираем пробелы до и после
            address = str(address).strip()
            if not re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", address):
                raise ValueError(f"Некорректный формат email адреса: {address}")
            # Возвращаем очищенный и переведенный в нижний регистр email
            return address.lower()
        return address

    @validates("age")
    def validate_age(self, key, age):
        if age is not None:
            age = int(age)
            if age < 0 or age > 120:
                raise ValueError(
                    f"Возраст должен быть от 0 до 120 лет, передано: {age}"
                )
        return age

    @validates("full_name")
    def validate_full_name(self, key, name):
        if name:
            # Убираем пробелы по краям и делаем Каждое Слово С Большой Буквы
            name = str(name).strip().title()

            if len(name) < 2:
                raise ValueError("Имя слишком короткое (минимум 2 символа)")
            if not re.match(r"^[A-Za-zА-Яа-яЁё\s\-]+$", name):
                raise ValueError(f"Имя должно содержать только буквы: {name}")
        return name

    deletion_requests = relationship(
        "DeletionRequest", back_populates="user", cascade="all, delete-orphan"
    )

    def __str__(self):
        return f"{self.username} ({self.email})"


class DeletionRequest(Base):
    __tablename__ = "deletion_requests"

    id = Column(Integer, primary_key=True, index=True)
    # ondelete="CASCADE" означает, что если удалить юзера, все его заявки тоже удалятся
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    requested_by = Column(String, nullable=False)
    status = Column(String, default="pending")  # Статусы: pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="deletion_requests")
