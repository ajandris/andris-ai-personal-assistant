from fastapi.testclient import TestClient
from app.main import app


def test_homepage_status_code():
    """GET / возвращает HTTP 200."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200


def test_homepage_html_lang_ru():
    """Главная страница содержит <html lang="ru">."""
    client = TestClient(app)
    response = client.get("/")
    assert '<html lang="ru">' in response.text


def test_homepage_author_name():
    """Главная страница содержит имя автора «Андрис Янчевскис»."""
    client = TestClient(app)
    response = client.get("/")
    assert "Андрис Янчевскис" in response.text


def test_homepage_ai_assistant_section():
    """Главная страница содержит раздел «AI-ассистент»."""
    client = TestClient(app)
    response = client.get("/")
    assert "AI-ассистент" in response.text
    assert 'id="ai-assistant"' in response.text


def test_homepage_no_lorem_ipsum():
    """Главная страница не содержит 'Lorem ipsum'."""
    client = TestClient(app)
    response = client.get("/")
    assert "lorem ipsum" not in response.text.lower()


def test_static_css_accessible():
    """Основной CSS-файл доступен через маршрут статических файлов."""
    client = TestClient(app)
    response = client.get("/static/css/styles.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")
    assert "--accent-primary" in response.text


def test_static_js_accessible():
    """Основной JS-файл доступен через маршрут статических файлов."""
    client = TestClient(app)
    response = client.get("/static/js/chat.js")
    assert response.status_code == 200
    assert "initAIAssistantChat" in response.text


def test_api_chat_honest_notice():
    """POST /api/chat возвращает честное сообщение о подготовке интеграции."""
    client = TestClient(app)
    response = client.post(
        "/api/chat",
        json={"message": "Какой опыт разработки у Андриса?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "preparing"
    assert "Подключение AI-ассистента подготавливается" in data["reply"]
