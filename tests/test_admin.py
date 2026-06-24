from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_admin_panel_accessible():
    # Проверяем, что главная страница админки открывается
    response = client.get("/admin/")
    assert response.status_code == 200
    assert "Панель управления" in response.text


def test_admin_user_list_accessible():
    # Проверяем, что страница со списком пользователей работает
    response = client.get("/admin/user/list")
    assert response.status_code == 200


def test_health_check():
    # Проверяем, что технический эндпоинт отдает 200 OK
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirect():
    # Проверяем серверный редирект с главной страницы
    # follow_redirects=False нужен, чтобы поймать сам момент перенаправления (код 30x)
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 303, 307, 308)
    assert "/admin" in response.headers.get("location", "")
