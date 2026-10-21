"""Tests for AI Sales Agent, FAISS RAG retrieval, and lead capture with email notifications."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.schemas.chat import ChatMessage, ChatRequest, LeadCaptureRequest
from app.services.sales_agent import sales_agent_service


@pytest.fixture
def client():
    return TestClient(app)


def test_sales_agent_extract_contacts():
    """Тест извлечения email, телефона и telegram из текста."""
    text1 = "Здравствуйте, меня зовут Иван. Мой email ivan.petrov@company.com, свяжитесь со мной."
    res1 = sales_agent_service.extract_contacts_from_text(text1)
    assert res1["email"] == "ivan.petrov@company.com"

    text2 = "Мой телефон +44 7752 194449 или пишите в тг @ivan_recruiter"
    res2 = sales_agent_service.extract_contacts_from_text(text2)
    assert res2["telegram"] == "@ivan_recruiter"
    assert res2["phone"] is not None


def test_sales_agent_retrieve_rag_context():
    """Тест поиска по FAISS векторной базе знаний."""
    import asyncio
    hits = asyncio.run(sales_agent_service.retrieve_context("Python FastAPI RAG", top_k=3))
    assert len(hits) > 0
    assert any("Python" in h.get("title", "") or "RAG" in h.get("text", "") for h in hits)
    for h in hits:
        assert "score" in h
        assert "category" in h
        assert "source" in h


def test_api_chat_demand_comparison(client):
    """Тест эндпоинта /api/chat с сопоставлением требований к вакансии."""
    req = {
        "message": "Ищем бэкенд разработчика со знанием Python, FastAPI и PostgreSQL. Подходит ли Андрис?",
        "history": [],
    }
    response = client.post("/api/chat", json=req)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["reply"]) > 50
    assert len(data["sources"]) > 0
    # Проверяем, что в ответе упомянут Андрис или совпадения
    reply_text = data["reply"].lower()
    assert "андрис" in reply_text or "python" in reply_text


def test_api_chat_lead_contact_detection(client):
    """Тест автоматического перехвата контактов в чате и отправки лида."""
    with patch("app.services.sales_agent.send_smtp_email_async", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        req = {
            "message": "Отличный профиль! Мой email recruiter@acme-corp.com, напишите нам для оффера.",
            "history": [],
        }
        response = client.post("/api/chat", json=req)
        assert response.status_code == 200
        data = response.json()
        assert data["contact_captured"] is True
        assert data["status"] == "lead_captured"
        # Проверяем, что вызов SMTP отправки был инициирован
        settings = get_settings()
        if settings.smtp_host:
            assert mock_send.called


def test_api_chat_direct_lead_submission(client):
    """Тест отправки лида через форму быстрого захвата /api/chat/lead."""
    with patch("app.api.routes.verify_recaptcha", new_callable=AsyncMock) as mock_recaptcha, \
         patch("app.services.sales_agent.send_smtp_email_async", new_callable=AsyncMock) as mock_send, \
         patch("app.services.sales_agent.send_acknowledgement_email_async", new_callable=AsyncMock) as mock_ack:
        mock_recaptcha.return_value = True
        mock_send.return_value = True
        mock_ack.return_value = True

        payload = {
            "name": "Алексей Смирнов",
            "email": "alexey.smirnov@techstartup.io",
            "phone": "+44 7700 900123",
            "demands": "Нужен RAG AI ассистент для сайта компании",
            "notes": "Готовы обсудить на этой неделе",
            "recaptcha_token": "valid_mock_token",
        }
        response = client.post("/api/chat/lead", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "Алексей Смирнов" in data["message"]
        assert data["message_id"] is not None


def test_api_chat_direct_lead_recaptcha_rejected(client):
    """Тест отклонения отправки лида при непройденной reCAPTCHA."""
    with patch("app.api.routes.verify_recaptcha", new_callable=AsyncMock) as mock_recaptcha:
        mock_recaptcha.return_value = False

        payload = {
            "name": "Спам Бот",
            "email": "bot@spam.com",
            "recaptcha_token": "invalid_token",
        }
        response = client.post("/api/chat/lead", json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "reCAPTCHA" in data.get("detail", "")


def test_ai_assistant_page_renders_sales_agent_and_recaptcha(client):
    """Тест отображения страницы AI-ассистента с элементами AI Agent, RAG и reCAPTCHA."""
    response = client.get("/ai-assistant")
    assert response.status_code == 200
    assert "AI &amp; Competency Agent" in response.text
    assert "Sales" not in response.text
    assert "FAISS" in response.text
    assert "OpenAI" in response.text
    assert "direct-lead-form" in response.text
    assert "quick-contact-card" in response.text
    assert "g-recaptcha" in response.text
    assert "recaptcha/api.js" in response.text
