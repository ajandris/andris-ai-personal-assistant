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


def test_homepage_brand_role():
    """Шапка содержит подпись роли «AI Agents»."""
    client = TestClient(app)
    response = client.get("/")
    assert '<span class="brand-role">AI Agents</span>' in response.text


def test_homepage_ai_assistant_section():
    """Главная страница содержит ссылку и информирование об AI-ассистенте."""
    client = TestClient(app)
    response = client.get("/")
    assert "AI-ассистент" in response.text
    assert 'href="/ai-assistant"' in response.text


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


def test_homepage_uses_base_template():
    """Главная страница наследует базовый шаблон с шапкой и подвалом."""
    client = TestClient(app)
    response = client.get("/")
    assert '<header class="site-header"' in response.text
    assert '<footer class="site-footer"' in response.text


def test_experience_page_route():
    """GET /experience возвращает страницу опыта работы."""
    client = TestClient(app)
    response = client.get("/experience")
    assert response.status_code == 200
    assert "Опыт работы" in response.text
    assert 'id="experience"' in response.text


def test_skills_page_route():
    """GET /skills возвращает страницу навыков."""
    client = TestClient(app)
    response = client.get("/skills")
    assert response.status_code == 200
    assert "Навыки" in response.text
    assert 'id="skills"' in response.text


def test_education_page_route():
    """GET /education возвращает страницу образования и обучения."""
    client = TestClient(app)
    response = client.get("/education")
    assert response.status_code == 200
    assert "Образование и обучение" in response.text
    assert 'id="education"' in response.text


def test_portfolio_page_route():
    """GET /portfolio возвращает страницу портфолио с проектами и ссылками."""
    client = TestClient(app)
    response = client.get("/portfolio")
    assert response.status_code == 200
    assert "Портфолио" in response.text
    assert 'id="portfolio"' in response.text
    assert "tic-tac-toe (крестики нолики)" in response.text
    assert "https://github.com/ajandris/my-public-face" in response.text
    assert "https://github.com/ajandris/tic-tac-toe" in response.text
    assert "https://github.com/ajandris/simpleshop" in response.text
    assert "https://github.com/ajandris/candlemania" in response.text
    assert "https://ajandris.github.io/my-public-face/" in response.text
    assert "https://ajandris.github.io/tic-tac-toe/" in response.text
    assert "https://theoldechristmasmarket.p.jancevskis.com/" in response.text
    assert "https://www.candlemania.p.jancevskis.com/" in response.text


def test_ai_assistant_page_route():
    """GET /ai-assistant возвращает страницу AI-ассистента."""
    client = TestClient(app)
    response = client.get("/ai-assistant")
    assert response.status_code == 200
    assert "AI-ассистент" in response.text
    assert 'id="ai-assistant"' in response.text


def test_active_menu_item_on_experience_page():
    """На странице /experience пункт меню «Опыт» отмечен как активный."""
    client = TestClient(app)
    response = client.get("/experience")
    assert response.status_code == 200
    assert 'href="/experience" class="nav-link active is-active" aria-current="page"' in response.text


def test_active_menu_item_on_skills_page():
    """На странице /skills пункт меню «Навыки» отмечен как активный."""
    client = TestClient(app)
    response = client.get("/skills")
    assert response.status_code == 200
    assert 'href="/skills" class="nav-link active is-active" aria-current="page"' in response.text


def test_active_menu_item_on_education_page():
    """На странице /education пункт меню «Обучение» отмечен как активный."""
    client = TestClient(app)
    response = client.get("/education")
    assert response.status_code == 200
    assert 'href="/education" class="nav-link active is-active" aria-current="page"' in response.text


def test_active_menu_item_on_portfolio_page():
    """На странице /portfolio пункт меню «Портфолио» отмечен как активный."""
    client = TestClient(app)
    response = client.get("/portfolio")
    assert response.status_code == 200
    assert 'href="/portfolio" class="nav-link active is-active" aria-current="page"' in response.text


def test_active_menu_item_on_ai_assistant_page():
    """На странице /ai-assistant кнопка AI-ассистента в шапке отмечена как активная."""
    client = TestClient(app)
    response = client.get("/ai-assistant")
    assert response.status_code == 200
    assert 'href="/ai-assistant" class="btn btn-header-ai active is-active" aria-current="page"' in response.text


def test_css_contains_active_menu_item_styles():
    """В CSS присутствуют стили для выделения активного пункта меню."""
    client = TestClient(app)
    response = client.get("/static/css/styles.css")
    assert response.status_code == 200
    assert ".nav-link.active" in response.text
    assert 'aria-current="page"' in response.text


def test_homepage_contains_favicon_links():
    """Главная страница содержит ссылки на фавиконки в <head>."""
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert 'rel="icon" type="image/svg+xml" href="/static/images/favicon.svg"' in response.text
    assert 'rel="icon" type="image/png" sizes="32x32" href="/static/images/favicon-32x32.png"' in response.text
    assert 'rel="icon" type="image/png" sizes="16x16" href="/static/images/favicon-16x16.png"' in response.text
    assert 'rel="apple-touch-icon" sizes="180x180" href="/static/images/apple-touch-icon.png"' in response.text
    assert 'rel="shortcut icon" href="/static/images/favicon.ico"' in response.text


def test_favicon_ico_route():
    """Маршрут /favicon.ico доступен и возвращает иконку."""
    client = TestClient(app)
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert len(response.content) > 0


def test_static_favicons_accessible():
    """Файлы фавиконок доступны через /static/images."""
    client = TestClient(app)
    for path in [
        "/static/images/favicon.svg",
        "/static/images/favicon-32x32.png",
        "/static/images/favicon-16x16.png",
        "/static/images/apple-touch-icon.png",
        "/static/images/favicon.ico",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert len(response.content) > 0



