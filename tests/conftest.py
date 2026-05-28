import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.database import Base
from app.models import User


# Фикстура поднимает контейнер на время всей тестовой сессии
@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine", dbname="testdb") as postgres:
        yield postgres


# Формируем URL для подключения к временной базе
@pytest.fixture(scope="session")
def db_url(postgres_container):
    host = postgres_container.get_container_host_ip()
    port = postgres_container.get_exposed_port(5432)
    user = postgres_container.username
    password = postgres_container.password
    db = postgres_container.dbname
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


@pytest.fixture
def engine(db_url):
    return create_async_engine(db_url, echo=False)


# Перед каждым тестом создаем таблицы, после — удаляем
@pytest.fixture(autouse=True)
async def setup_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Выдаем сессию БД для самого теста
@pytest.fixture
async def db_session(engine):
    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session
