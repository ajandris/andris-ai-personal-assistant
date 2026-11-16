"""Сервис чата AI-ассистента сайта.

Ответы строит ядро app/rag/assistant_core.py с настройками лучшего варианта
этапа 4 (значения AssistantConfig по умолчанию): база знаний A v3, таблица
ключевых слов, промпты intent_v2 и answer_v4. Это та же реализация, что и в
финальном ноутбуке.

Сервис также перехватывает контакты, которые посетитель оставил в сообщении
(email, телефон, Telegram), сохраняет их и отправляет уведомление Андрису.
Готовых ответов нет: если модель недоступна, посетитель получает честное
сообщение об ошибке и ссылку на форму «Контакты».
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI

from app.core.config import Settings, get_settings
from app.rag.assistant_core import (
    DEFAULT_INDEX_DIR,
    DEFAULT_KEYWORDS_PATH,
    DEFAULT_PROMPTS_DIR,
    DEFAULT_RECORDS_PATH,
    AssistantConfig,
    AssistantError,
    AssistantResponse,
    load_keywords,
    load_or_build_index,
    load_prompts,
    run_assistant,
)
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    LeadCaptureRequest,
    LeadCaptureResponse,
    SourceItem,
)
from app.services.contact_service import (
    mark_email_sent,
    save_message_to_db,
    send_acknowledgement_email_async,
    send_smtp_email_async,
)

logger = logging.getLogger(__name__)

# Regular expressions for contact extraction
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"(?:\+?\d{1,4}[-.\s]?)?\(?\d{2,5}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}")
TELEGRAM_REGEX = re.compile(r"(?:@|t\.me/)([a-zA-Z0-9_]{4,32})")

ERROR_REPLY = (
    "Ассистент сейчас не может ответить: не удалось обратиться к языковой модели. "
    "Попробуйте повторить вопрос позже или напишите Андрису через форму на странице "
    "[«Контакты»](/contact)."
)
LEAD_ACK = "Спасибо! Ваши контакты и сообщение переданы Андрису — он свяжется с вами."


class SalesAgentService:
    """Чат сайта: ядро ассистента (RAG A v3) и передача контактов посетителя Андрису."""

    def __init__(self, settings: Optional[Settings] = None, config: Optional[AssistantConfig] = None,
                 records_path: Path = DEFAULT_RECORDS_PATH, keywords_path: Path = DEFAULT_KEYWORDS_PATH,
                 prompts_dir: Path = DEFAULT_PROMPTS_DIR, index_dir: Path = DEFAULT_INDEX_DIR) -> None:
        self.settings = settings or get_settings()
        self._config = config
        self.records_path = Path(records_path)
        self.keywords_path = Path(keywords_path)
        self.prompts_dir = Path(prompts_dir)
        self.index_dir = Path(index_dir)
        self._knowledge: Optional[Dict[str, Any]] = None
        self._lock = threading.Lock()

    @property
    def config(self) -> AssistantConfig:
        """Настройки ассистента: лучший вариант этапа 4, модели — из .env (если заданы)."""
        if self._config is None:
            self._config = replace(AssistantConfig(), llm_model=self.settings.effective_llm_model,
                                   embedding_model=self.settings.effective_embedding_model)
        return self._config

    def _get_openai_client(self) -> OpenAI:
        """Create authenticated OpenAI client."""
        api_key = self.settings.openai_api_key
        if not api_key:
            raise AssistantError("OPENAI_API_KEY не задан в настройках или переменных окружения")
        return OpenAI(api_key=api_key)

    def knowledge(self, client: Any) -> Dict[str, Any]:
        """Индекс, фрагменты, промпты и таблица ключевых слов (загружаются один раз).

        Индекс FAISS хранится в index_dir и строится заново, только если изменился
        файл базы знаний или настройки фрагментов и эмбеддингов.
        """
        with self._lock:
            if self._knowledge is None:
                index, chunks = load_or_build_index(client, self.config, self.records_path, self.index_dir)
                self._knowledge = {
                    "index": index,
                    "chunks": chunks,
                    "prompts": load_prompts(self.config, self.prompts_dir),
                    "keywords": load_keywords(self.keywords_path) if self.keywords_path.exists() else {},
                }
            return self._knowledge

    def answer_question(self, question: str, client: Any = None) -> AssistantResponse:
        """Один вопрос посетителя: намерение → поиск по базе → ответ по найденным фрагментам."""
        client = client or self._get_openai_client()
        kb = self.knowledge(client)
        return run_assistant(question, client, kb["index"], kb["chunks"], self.config, kb["prompts"],
                             kb["keywords"])

    def build_sources(self, response: AssistantResponse) -> List[SourceItem]:
        """Источники, на которые сослалась модель, в формате виджета чата."""
        kb = self._knowledge or {"chunks": []}
        by_chunk = {chunk["chunk_id"]: chunk for chunk in kb["chunks"]}
        hits = response.log.get("hits", [])
        items = []
        for source in response.sources:
            hit = hits[source["number"] - 1] if 0 < source["number"] <= len(hits) else {}
            chunk = by_chunk.get(hit.get("chunk_id", ""), {})
            url = source["source_url"]
            items.append(SourceItem(
                title=source["title"],
                category=chunk.get("entity_type", "knowledge_base"),
                source=source["record_id"],
                url=url if url.startswith(("/", "http://", "https://")) else None,
                score=hit.get("score"),
            ))
        return items

    def extract_contacts_from_text(self, text: str) -> Dict[str, Optional[str]]:
        """Extract email, phone, and telegram handles from natural text."""
        emails = EMAIL_REGEX.findall(text)
        phones = PHONE_REGEX.findall(text)
        tgs = TELEGRAM_REGEX.findall(text)

        # Filter out obviously false phone matches (e.g. single numbers or years like 2026)
        valid_phones = [p.strip() for p in phones if len(re.sub(r"\D", "", p)) >= 7 and not (len(p.strip()) == 4 and p.strip().startswith("20"))]

        return {
            "email": emails[0] if emails else None,
            "phone": valid_phones[0] if valid_phones else None,
            "telegram": f"@{tgs[0]}" if tgs else None,
        }

    async def _capture_contacts(self, name: str, email: Optional[str], phone: Optional[str], user_message: str,
                                settings: Settings) -> bool:
        """Сохраняет контакты из сообщения и отправляет уведомление Андрису. Возвращает email_sent."""
        contact_str = f"Email: {email or 'Не указан'}, Телефон/Телеграм: {phone or 'Не указан'}"
        full_lead_message = (
            f"Новый лид от AI-ассистента!\n\n"
            f"Имя: {name}\n"
            f"Контакты: {contact_str}\n"
            f"Последнее сообщение / запрос посетителя:\n{user_message}\n"
        )
        email_sent = False
        try:
            msg_id = save_message_to_db(
                name=name,
                email_addr=email or "unknown@lead.assistant",
                subject=f"[AI Lead] Контакты от {name}",
                message=full_lead_message,
                settings=settings,
            )
            if settings.smtp_host:
                email_sent = await send_smtp_email_async(
                    name=f"{name} (AI Lead)",
                    email_addr=email or settings.smtp_from_email,
                    subject=f"[AI Lead] Новое обращение и контакты: {name}",
                    message=full_lead_message,
                    settings=settings,
                )
                if email_sent:
                    mark_email_sent(msg_id, settings)
                if email:
                    await send_acknowledgement_email_async(
                        name=name,
                        email_addr=email,
                        subject="Получение вашего запроса к Андрису Янчевскису",
                        message=f"Здравствуйте, {name}!\n\nВаш запрос успешно передан Андрису. Спасибо за обращение!\n\nТекст вашего запроса:\n{user_message}",
                        settings=settings,
                    )
        except Exception as exc:
            logger.error("Failed to log or send lead email: %s", exc)
        return email_sent

    async def process_chat(self, request: ChatRequest, settings: Optional[Settings] = None) -> ChatResponse:
        """Отвечает на вопрос посетителя и, если в сообщении есть контакты, передаёт их Андрису.

        Ассистент отвечает на каждый вопрос отдельно (история диалога в ответ не
        передаётся): каждый ответ опирается только на найденные фрагменты базы.
        """
        current_settings = settings or self.settings
        user_message = request.message.strip()

        extracted = self.extract_contacts_from_text(user_message)
        contact_email = request.contact_email or extracted.get("email")
        contact_phone = request.contact_phone or extracted.get("phone") or extracted.get("telegram")
        contact_name = request.contact_name or "Посетитель сайта"
        contact_captured = bool(contact_email or contact_phone)
        email_sent = False
        if contact_captured:
            email_sent = await self._capture_contacts(contact_name, contact_email, contact_phone, user_message,
                                                      current_settings)

        try:
            response = await asyncio.to_thread(self.answer_question, user_message)
        except AssistantError as exc:
            logger.error("Assistant error: %s", exc)
            reply, status, sources = ERROR_REPLY, "error", []
        else:
            reply, status, sources = response.answer, response.status, self.build_sources(response)
            if contact_captured:
                # Если посетитель только оставил контакты, ответ ассистента о форме не нужен.
                reply = LEAD_ACK if response.status == "contact" else f"{LEAD_ACK}\n\n{reply}"

        return ChatResponse(
            reply=reply,
            status="lead_captured" if contact_captured else status,
            sources=sources,
            contact_captured=contact_captured,
            email_sent=email_sent,
        )

    async def capture_direct_lead(self, lead: LeadCaptureRequest, settings: Optional[Settings] = None) -> LeadCaptureResponse:
        """Handle direct lead submission from chat UI form modal."""
        current_settings = settings or self.settings

        full_message = (
            f"Новый лид из формы AI-ассистента!\n\n"
            f"Имя: {lead.name}\n"
            f"Email: {lead.email}\n"
            f"Телефон/Telegram: {lead.phone or 'Не указан'}\n\n"
            f"Требования к проекту / вакансии:\n{lead.demands or 'Не указаны'}\n\n"
            f"Дополнительные заметки:\n{lead.notes or 'Нет'}\n"
        )

        msg_id = save_message_to_db(
            name=lead.name,
            email_addr=lead.email,
            subject=f"[AI Lead] Новая заявка: {lead.name}",
            message=full_message,
            settings=current_settings,
        )

        email_sent = False
        if current_settings.smtp_host:
            email_sent = await send_smtp_email_async(
                name=f"{lead.name} (Direct Lead)",
                email_addr=lead.email,
                subject=f"[AI Lead] Новая заявка на сотрудничество от {lead.name}",
                message=full_message,
                settings=current_settings,
            )
            if email_sent:
                mark_email_sent(msg_id, current_settings)

            await send_acknowledgement_email_async(
                name=lead.name,
                email_addr=lead.email,
                subject="Подтверждение получения: Ваш запрос к Андрису Янчевскису",
                message=(
                    f"Здравствуйте, {lead.name}!\n\n"
                    f"Благодарим за интерес к сотрудничеству с Андрисом Янчевскисом. "
                    f"Ваши требования и контакты успешно переданы. Андрис свяжется с вами в ближайшее время.\n\n"
                    f"С уважением,\nAI Agent Андриса Янчевскиса"
                ),
                settings=current_settings,
            )

        return LeadCaptureResponse(
            success=True,
            message=f"Спасибо, {lead.name}! Ваши контакты и требования успешно отправлены Андрису.",
            email_sent=email_sent,
            message_id=msg_id,
        )


# Singleton instance
sales_agent_service = SalesAgentService()
