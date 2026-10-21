"""Sales Agent service module with FAISS RAG and OpenAI integration.

Compares visitor project/job requirements with Andris Jancevskis' verified skills,
provides structured comparisons, captures lead contact details, and dispatches
notification emails to the configured email address.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

from app.core.config import Settings, get_settings
from app.rag.vector_store import FAISSVectorStore
from app.schemas.chat import (
    ChatMessage,
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


class SalesAgentService:
    """Sales Agent orchestrator combining FAISS RAG, OpenAI LLM, and lead notifications."""

    def __init__(self, vector_store: Optional[FAISSVectorStore] = None, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self._vector_store = vector_store

    @property
    def vector_store(self) -> FAISSVectorStore:
        """Lazily load or return the FAISS vector store."""
        if self._vector_store is None:
            rag_path = Path(self.settings.vector_db_path)
            try:
                self._vector_store = FAISSVectorStore.load(rag_path)
                logger.info("Loaded existing FAISS store with %d chunks", self._vector_store.count())
            except Exception as exc:
                logger.warning("Could not load FAISS store from %s: %s. Creating empty store.", rag_path, exc)
                self._vector_store = FAISSVectorStore(dimension=1536, metric="cosine")
        return self._vector_store

    def _get_openai_client(self) -> OpenAI:
        """Create authenticated OpenAI client."""
        api_key = self.settings.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured in settings or environment")
        return OpenAI(api_key=api_key)

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

    async def retrieve_context(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """Retrieve top_k most relevant documents from FAISS store."""
        try:
            client = self._get_openai_client()
            embedding_model = self.settings.effective_embedding_model
            response = client.embeddings.create(input=query, model=embedding_model)
            q_vector = response.data[0].embedding
            return self.vector_store.search(q_vector, top_k=top_k)
        except Exception as exc:
            logger.error("Error during RAG retrieval: %s", exc)
            return []

    async def process_chat(self, request: ChatRequest, settings: Optional[Settings] = None) -> ChatResponse:
        """Process incoming visitor message through RAG retrieval, sales comparison, and lead detection."""
        current_settings = settings or self.settings
        user_message = request.message.strip()

        # 1. Detect if contact details were passed directly or written in the message
        extracted = self.extract_contacts_from_text(user_message)
        contact_email = request.contact_email or extracted.get("email")
        contact_phone = request.contact_phone or extracted.get("phone") or extracted.get("telegram")
        contact_name = request.contact_name or "Посетитель сайта"

        contact_captured = bool(contact_email or contact_phone)
        email_sent = False

        # 2. Retrieve relevant context from FAISS RAG
        retrieved_docs = await self.retrieve_context(user_message, top_k=4)

        sources: List[SourceItem] = []
        context_snippets: List[str] = []
        for doc in retrieved_docs:
            sources.append(
                SourceItem(
                    title=doc.get("title", "Фрагмент базы знаний"),
                    category=doc.get("category", "skills"),
                    source=doc.get("source", "База знаний"),
                    url=doc.get("url"),
                    score=doc.get("score"),
                )
            )
            snippet = (
                f"### {doc.get('title')}\n"
                f"Категория: {doc.get('category')} | Источник: {doc.get('source')}\n"
                f"{doc.get('text')}\n"
            )
            context_snippets.append(snippet)

        context_block = "\n---\n".join(context_snippets) if context_snippets else "Контекст не найден."

        # 3. If contact details were captured, log to DB and send email notification
        if contact_captured:
            contact_str = f"Email: {contact_email or 'Не указан'}, Телефон/Телеграм: {contact_phone or 'Не указан'}"
            full_lead_message = (
                f"Новый лид от AI-ассистента!\n\n"
                f"Имя: {contact_name}\n"
                f"Контакты: {contact_str}\n"
                f"Последнее сообщение / запрос посетителя:\n{user_message}\n"
            )
            try:
                msg_id = save_message_to_db(
                    name=contact_name,
                    email_addr=contact_email or "unknown@lead.assistant",
                    subject=f"[AI Lead] Контакты от {contact_name}",
                    message=full_lead_message,
                    settings=current_settings,
                )
                if current_settings.smtp_host:
                    email_sent = await send_smtp_email_async(
                        name=f"{contact_name} (AI Lead)",
                        email_addr=contact_email or current_settings.smtp_from_email,
                        subject=f"[AI Lead] Новое обращение и контакты: {contact_name}",
                        message=full_lead_message,
                        settings=current_settings,
                    )
                    if email_sent:
                        mark_email_sent(msg_id, current_settings)

                    if contact_email:
                        await send_acknowledgement_email_async(
                            name=contact_name,
                            email_addr=contact_email,
                            subject="Получение вашего запроса к Андрису Янчевскису",
                            message=f"Здравствуйте, {contact_name}!\n\nВаш запрос успешно передан Андрису. Спасибо за обращение!\n\nТекст вашего запроса:\n{user_message}",
                            settings=current_settings,
                        )
            except Exception as exc:
                logger.error("Failed to log or send lead email: %s", exc)

        # 4. Construct System Prompt and LLM completion
        system_prompt = (
            "Ты — интеллектуальный AI & Competency Agent (AI-ассистент по компетенциям) Андриса Янчевскиса.\n"
            "Твоя задача — профессионально, доброжелательно и аргументированно помочь посетителю (рекрутеру, клиенту, "
            "техническому директору или основателю проекта) сопоставить его требования, задачи или вакансию с реальными "
            "подтверждёнными навыками, проектами и опытом Андриса Янчевскиса.\n\n"
            "ПРАВИЛА И СТРУКТУРА ОТВЕТА:\n"
            "1. Сопоставление требований с компетенциями (Матчинг):\n"
            "   - ✅ **Прямые совпадения**: Четко выдели технологии, инструменты и задачи, в которых у Андриса есть подтверждённый опыт (Python, FastAPI, Django, SQL/PostgreSQL, RAG, FAISS, LLM, системный анализ, PRINCE2, WMS).\n"
            "   - 💡 **Смежные компетенции и преимущества**: Обрати внимание на сильные стороны: глубокое понимание архитектуры баз данных (системные каталоги PostgreSQL), математический и Big Data бэкграунд (диплом Wrexham Glyndwr), диплом бакалавра Open University, опыт управления проектами и людьми.\n"
            "   - ⚠️ **Честные границы (Честность без галлюцинаций)**: Если в запросе упомянуты технологии, которых нет в подтвержденной базе знаний (например, Swift, C++, узкий мобильный DevOps), прямо и открыто скажи, что подтверждённого опыта с ними нет, не придумывай факты.\n"
            "   - 🔗 **Подтверждения проектами**: Ссылайся на реальные проекты из GitHub: TheDecisionPoint (Decision Intelligence AI платформа), postgres_db_desc (CLI-интроспекция PostgreSQL), candlemania, simpleshop, andris-ai-personal-assistant.\n"
            "2. Сбор контактов (Call to Action / Lead Generation):\n"
            f"   - Состояние контакта: {'КОНТАКТЫ ПОЛУЧЕНЫ!' if contact_captured else 'Контакты пока не получены.'}\n"
            "   - Если контакты ТОЛЬКО ЧТО получены ({'Да' if contact_captured else 'Нет'}): Поблагодари посетителя, тепло подтверди, что информация и запрос переданы напрямую Андрису на его почту, и он свяжется в самое ближайшее время.\n"
            "   - Если контакты ЕЩЁ НЕ получены: Всегда в конце ответа дружелюбно и ненавязчиво предложи посетителю оставить свои контакты (имя, email, телефон или Telegram), чтобы Андрис мог обсудить детали проекта, подготовить предложение или договориться о звонке/интервью.\n"
            "3. Язык общения: Отвечай на языке запроса пользователя (по умолчанию — русский).\n"
            "4. Форматирование: Используй четкий структурированный Markdown (списки, жирный шрифт, акценты), отвечай по существу и вдохновляюще.\n\n"
            f"ПОДТВЕРЖДЁННЫЙ КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ (RAG):\n{context_block}"
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

        # Add recent conversation history if provided
        if request.history:
            for h in request.history[-6:]:
                messages.append({"role": h.role, "content": h.content})

        messages.append({"role": "user", "content": user_message})

        try:
            client = self._get_openai_client()
            llm_model = current_settings.effective_llm_model
            completion = client.chat.completions.create(
                model=llm_model,
                messages=messages,
                temperature=0.3,
            )
            reply = completion.choices[0].message.content or ""
        except Exception as exc:
            logger.error("Error from OpenAI chat completion: %s", exc)
            reply = (
                f"Благодарю за вопрос! Андрис Янчевскис обладает подтверждённым опытом в Python (FastAPI, Django), "
                f"реляционных базах данных (PostgreSQL, SQL), проектировании RAG AI-ассистентов и системном анализе. "
                f"Вы можете оставить ваши контакты или связаться с Андрисом напрямую по email: andris.jancevskis@gmail.com."
            )

        return ChatResponse(
            reply=reply,
            status="lead_captured" if contact_captured else "ok",
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
