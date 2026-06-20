import json
import os
from datetime import datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import User

BACKUP_DIR = "backups"


async def create_backup():
    # Создаем папку, если её нет
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

        # Если база пуста, не перезаписываем бэкап пустотой
        if not users:
            return

        # Сериализуем данные
        data = []
        for u in users:
            data.append(
                {
                    "username": u.username,
                    "email": u.email,
                    "full_name": u.full_name,
                    "age": u.age,
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
            )

        # Записываем в файл
        filepath = os.path.join(BACKUP_DIR, "users_backup.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print(
            f"[{datetime.now()}] Успешный бэкап {len(data)} пользователей в {filepath}"
        )
