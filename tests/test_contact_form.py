import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.contact_service import get_all_messages, get_db_path, init_db, save_message_to_db


def test_contact_page_contains_form():
    """На странице /contact присутствует форма обратной связи с необходимыми полями."""
    client = TestClient(app)
    response = client.get("/contact")
    assert response.status_code == 200
    assert 'id="contact-form"' in response.text
    assert 'name="name"' in response.text
    assert 'name="email"' in response.text
    assert 'name="message"' in response.text
    assert 'id="contact-submit-btn"' in response.text
    assert "Написать сообщение" in response.text
    assert "recaptcha/api.js" in response.text
    assert "g-recaptcha" in response.text


def test_submit_contact_form_success(tmp_path):
    """POST /api/contact сохраняет сообщение в SQLite и возвращает статус success."""
    test_db = tmp_path / "test_messages.db"
    settings = get_settings()

    with patch.object(settings, "sqlite_db_path", str(test_db)), \
         patch("app.api.routes.verify_recaptcha", return_value=True):
        client = TestClient(app)
        payload = {
            "name": "Алексей Смирнов",
            "email": "alexey@example.com",
            "subject": "Предложение о сотрудничестве",
            "message": "Здравствуйте! Хотим обсудить разработку AI-ассистента для нашей компании.",
            "recaptcha_token": "test-valid-token",
        }
        response = client.post("/api/contact", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["message_id"] is not None
        assert "успешно отправлено" in data["message"]

        # Проверка записи в базе данных SQLite
        messages = get_all_messages(settings=settings)
        assert len(messages) >= 1
        saved = messages[0]
        assert saved["name"] == "Алексей Смирнов"
        assert saved["email"] == "alexey@example.com"
        assert saved["subject"] == "Предложение о сотрудничестве"
        assert "разработку AI-ассистента" in saved["message"]


def test_submit_contact_form_form_encoded(tmp_path):
    """POST /api/contact поддерживает form-encoded данные из стандартной HTML-формы."""
    test_db = tmp_path / "form_encoded.db"
    settings = get_settings()

    with patch.object(settings, "sqlite_db_path", str(test_db)), \
         patch("app.api.routes.verify_recaptcha", return_value=True):
        client = TestClient(app)
        form_data = {
            "name": "Мария Иванова",
            "email": "maria@example.com",
            "subject": "Вопрос по проекту",
            "message": "Добрый день! Интересует опыт проектирования баз данных.",
            "g-recaptcha-response": "test-form-token",
        }
        response = client.post("/api/contact", data=form_data)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        messages = get_all_messages(settings=settings)
        assert any(m["name"] == "Мария Иванова" for m in messages)


def test_contact_form_recaptcha_rejected():
    """POST /api/contact возвращает 400 Bad Request при непройденной проверке reCAPTCHA."""
    with patch("app.api.routes.verify_recaptcha", return_value=False):
        client = TestClient(app)
        payload = {
            "name": "Тестовый Бот",
            "email": "bot@example.com",
            "subject": "Спам-сообщение",
            "message": "Сообщение без подтверждения капчи",
        }
        response = client.post("/api/contact", json=payload)
        assert response.status_code == 400
        assert "reCAPTCHA" in response.json()["detail"]


def test_submit_contact_form_validation_error():
    """POST /api/contact возвращает 422 при некорректном email, пустом сообщении или отсутствии темы."""
    client = TestClient(app)
    # Некорректный email
    response = client.post(
        "/api/contact",
        json={
            "name": "Тест",
            "email": "invalid-email-format",
            "subject": "Тема сообщения",
            "message": "Короткий текст сообщения",
        },
    )
    assert response.status_code == 422

    # Слишком короткое имя
    response = client.post(
        "/api/contact",
        json={
            "name": "A",
            "email": "valid@example.com",
            "subject": "Тема сообщения",
            "message": "Текст сообщения достаточной длины",
        },
    )
    assert response.status_code == 422

    # Отсутствующая тема сообщения (mandatory)
    response = client.post(
        "/api/contact",
        json={
            "name": "Алексей",
            "email": "valid@example.com",
            "message": "Текст сообщения достаточной длины",
        },
    )
    assert response.status_code == 422

    # Слишком короткая тема сообщения (меньше 5 символов)
    response = client.post(
        "/api/contact",
        json={
            "name": "Алексей",
            "email": "valid@example.com",
            "subject": "1234",
            "message": "Текст сообщения достаточной длины",
        },
    )
    assert response.status_code == 422

    # Тема из одних пробелов
    response = client.post(
        "/api/contact",
        json={
            "name": "Алексей",
            "email": "valid@example.com",
            "subject": "    ",
            "message": "Текст сообщения достаточной длины",
        },
    )
    assert response.status_code == 422


def test_database_placed_in_data_directory():
    """База данных сообщений по умолчанию создается в директории /data."""
    settings = get_settings()
    db_path = get_db_path(settings)
    assert "data" in db_path.parts
    # Инициализация и проверка структуры
    init_db(settings)
    assert db_path.exists()

    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='messages';")
        assert cursor.fetchone() is not None
        # Проверка наличия view 'massages'
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='massages';")
        assert cursor.fetchone() is not None


def test_smtp_mock_sending(tmp_path):
    """При настроенном SMTP отправляется почтовое сообщение."""
    test_db = tmp_path / "smtp_test.db"
    settings = get_settings()

    with patch.object(settings, "sqlite_db_path", str(test_db)), \
         patch.object(settings, "smtp_host", "smtp.example.com"), \
         patch.object(settings, "smtp_user", "sender@example.com"), \
         patch.object(settings, "smtp_to_email", "admin@jancevskis.com"), \
         patch("app.api.routes.verify_recaptcha", return_value=True), \
         patch("smtplib.SMTP") as mock_smtp:

        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        client = TestClient(app)
        payload = {
            "name": "Елена",
            "email": "elena@example.com",
            "subject": "Тест SMTP",
            "message": "Проверка отправки почты через SMTP сервер.",
        }
        response = client.post("/api/contact", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["email_sent"] is True
        assert data["acknowledgement_sent"] is True
        # Одно письмо администратору и одно подтверждение отправителю
        assert mock_server.sendmail.call_count == 2
