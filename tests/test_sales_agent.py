"""Тесты чата сайта: ответы ядра ассистента, перехват контактов, форма лида.

Вместо OpenAI используется подставной клиент FakeClient из тестов ядра, поэтому
тесты не обращаются к API и не тратят деньги.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.rag.assistant_core import DEFAULT_PROMPTS_DIR, DEFAULT_RECORDS_PATH, load_records
from app.services.sales_agent import ERROR_REPLY, LEAD_ACK, SalesAgentService, sales_agent_service
from tests.test_assistant_core import FakeClient, make_record, write_jsonl


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def local_service(tmp_path):
    """Сервис с маленькой базой знаний во временной папке."""
    records = tmp_path / "records.jsonl"
    write_jsonl(records, [
        {**make_record("skill_fastapi", "Андрис Янчевскис разрабатывал API на FastAPI с PostgreSQL на стажировке.",
                       title="FastAPI"), "entity_type": "skill", "source_url": "/experience"},
        {**make_record("project_candlemania", "candlemania это блог о свечах а не интернет-магазин",
                       title="candlemania: назначение"), "entity_type": "project",
         "source_url": "author: сообщено в чате"},
    ])
    keywords = tmp_path / "keywords.csv"
    keywords.write_text("keyword,category,comment\ncandlemania,project,проект\n", encoding="utf-8")
    return SalesAgentService(settings=get_settings(), records_path=records, keywords_path=keywords,
                             prompts_dir=DEFAULT_PROMPTS_DIR, index_dir=tmp_path / "index")


def chat(client, service, fake, message):
    with patch("app.api.routes.sales_agent_service", service), \
         patch.object(service, "_get_openai_client", return_value=fake):
        return client.post("/api/chat", json={"message": message, "history": []})


def test_sales_agent_extract_contacts():
    """Тест извлечения email, телефона и telegram из текста."""
    text1 = "Здравствуйте, меня зовут Иван. Мой email ivan.petrov@company.com, свяжитесь со мной."
    res1 = sales_agent_service.extract_contacts_from_text(text1)
    assert res1["email"] == "ivan.petrov@company.com"

    text2 = "Мой телефон +44 7752 194449 или пишите в тг @ivan_recruiter"
    res2 = sales_agent_service.extract_contacts_from_text(text2)
    assert res2["telegram"] == "@ivan_recruiter"
    assert res2["phone"] is not None


def test_site_uses_best_stage4_configuration():
    """Сайт отвечает по базе A v3 с настройками лучшего варианта этапа 4."""
    config = sales_agent_service.config
    assert (config.intent_prompt_version, config.answer_prompt_version) == ("v2", "v4")
    assert config.strip_owner_name and config.kb_term_override
    assert sales_agent_service.records_path == DEFAULT_RECORDS_PATH
    assert sales_agent_service.records_path.parent.name == "rag_a_v3"
    assert sales_agent_service.keywords_path.exists()


def test_api_chat_answers_from_knowledge_base(client, local_service):
    """Ответ строится ядром ассистента по найденным фрагментам, источники передаются в виджет."""
    fake = FakeClient([
        json.dumps({"intent": "fact", "search_query": "FastAPI PostgreSQL API стажировка", "language": "ru"}),
        json.dumps({"answer": "Разрабатывал API на FastAPI с PostgreSQL [1].", "sufficient_context": True,
                    "used_sources": [1]}),
    ])
    response = chat(client, local_service, fake, "Есть ли у Андриса опыт с FastAPI?")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "answered"
    assert data["reply"] == "Разрабатывал API на FastAPI с PostgreSQL [1]."
    assert data["sources"][0]["title"] == "FastAPI"
    assert data["sources"][0]["url"] == "/experience"
    assert data["sources"][0]["category"] == "skill"
    assert data["contact_captured"] is False


def test_api_chat_keyword_table_overrides_off_topic(client, local_service):
    """Вопрос с ключевым словом из таблицы обрабатывается по базе, даже если шаг 1 счёл его не по теме."""
    fake = FakeClient([
        json.dumps({"intent": "off_topic", "search_query": "", "language": "ru"}),
        json.dumps({"answer": "Нет, это блог о свечах [1].", "sufficient_context": True, "used_sources": [1]}),
    ])
    data = chat(client, local_service, fake, "Правда ли что candlemania это интернет-магазин свечей").json()
    assert data["status"] == "answered"
    assert data["sources"][0]["url"] is None  # «author: …» — не ссылка


def test_api_chat_off_topic_is_refused_without_search(client, local_service):
    fake = FakeClient([json.dumps({"intent": "off_topic", "search_query": "", "language": "ru"})])
    data = chat(client, local_service, fake, "Какая погода в Лондоне?").json()
    assert data["status"] == "off_topic"
    assert len(fake.chat_calls) == 1


def test_api_chat_reports_provider_error_honestly(client, local_service):
    """Ошибка API — честное сообщение и ссылка на «Контакты», без готовых фактов и без email."""
    data = chat(client, local_service, FakeClient(fail_chat=True), "Какое у Андриса образование?").json()
    assert data["status"] == "error"
    assert data["reply"] == ERROR_REPLY
    assert "@" not in data["reply"] and "/contact" in data["reply"]
    assert data["sources"] == []


def test_api_chat_lead_contact_detection(client, local_service):
    """Контакты из сообщения перехватываются и передаются Андрису."""
    fake = FakeClient([json.dumps({"intent": "contact", "search_query": "", "language": "ru"})])
    with patch("app.services.sales_agent.save_message_to_db", return_value=1), \
         patch("app.services.sales_agent.send_smtp_email_async", new_callable=AsyncMock) as mock_send, \
         patch("app.services.sales_agent.send_acknowledgement_email_async", new_callable=AsyncMock):
        mock_send.return_value = True
        data = chat(client, local_service, fake,
                    "Отличный профиль! Мой email recruiter@acme-corp.com, напишите нам для оффера.").json()
    assert data["contact_captured"] is True
    assert data["status"] == "lead_captured"
    assert data["reply"] == LEAD_ACK
    if get_settings().smtp_host:
        assert mock_send.called


def test_build_index_script_uses_service(tmp_path, local_service):
    from scripts.build_rag_knowledge_base import main

    fake = FakeClient()
    with patch.object(local_service, "_get_openai_client", return_value=fake):
        assert main(local_service) == 0
    assert (tmp_path / "index" / "index.faiss").exists()
    assert (tmp_path / "index" / "fingerprint.json").exists()


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


def test_ai_assistant_page_shows_actual_number_of_records(client):
    """На странице ассистента — фактическое число записей базы, а не устаревшие «21 документ»."""
    response = client.get("/ai-assistant")
    count = len(load_records(DEFAULT_RECORDS_PATH, site="ru"))
    assert f"по {count} подтверждённым записям" in response.text
    assert "21 подтверждённому документу" not in response.text


def test_site_never_shows_owner_email():
    """Адрес электронной почты на сайте не публикуется (в том числе в сообщениях об ошибках)."""
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    for path in [root / "app" / "static" / "js" / "chat.js", root / "app" / "services" / "sales_agent.py",
                 *sorted((root / "app" / "templates").glob("*.html"))]:
        assert "andris.jancevskis@gmail.com" not in path.read_text(encoding="utf-8"), path
