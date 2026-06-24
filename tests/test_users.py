import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import User


@pytest.mark.asyncio
async def test_create_user(db_session):
    user = User(username="testuser", email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    assert user.id is not None
    assert user.username == "testuser"


@pytest.mark.asyncio
async def test_unique_username_constraint(db_session):
    user1 = User(username="unique_user", email="a@test.com")
    db_session.add(user1)
    await db_session.commit()

    user2 = User(username="unique_user", email="b@test.com")
    db_session.add(user2)

    with pytest.raises(Exception):
        await db_session.commit()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_get_user(db_session):
    user = User(username="findme", email="find@test.com")
    db_session.add(user)
    await db_session.commit()

    result = await db_session.execute(select(User).where(User.username == "findme"))
    found = result.scalar_one()

    assert found.email == "find@test.com"


@pytest.mark.asyncio
async def test_user_consent_default(db_session):
    # Создаем пользователя, не передавая поле consent_personal_data
    user = User(username="consent_test", email="consent@test.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Убеждаемся, что база данных сама проставила True
    assert user.consent_personal_data is True
