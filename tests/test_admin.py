from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)

def test_admin_panel_accessible():
    # Проверяем, что главная страница админки открывается
    response = client.get("/admin/")
    assert response.status_code == 200
    assert "Admin" in response.text

def test_admin_user_list_accessible():
    # Проверяем, что страница со списком пользователей работает
    response = client.get("/admin/user/list")
    assert response.status_code == 200
