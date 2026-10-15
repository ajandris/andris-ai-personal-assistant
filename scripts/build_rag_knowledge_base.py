"""Script to collect knowledge base from Site, GitHub, and CV,
generate OpenAI embeddings, and build the FAISS vector database in ./rag.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env
load_dotenv(ROOT_DIR / ".env")

from app.core.config import settings
from app.rag.vector_store import FAISSVectorStore
from openai import OpenAI


def get_raw_knowledge_documents() -> List[Dict[str, Any]]:
    """Assemble verified knowledge documents from Site, CV, and GitHub."""
    docs = [
        # ---------------- PROFILE & OVERVIEW ----------------
        {
            "id": "profile_overview",
            "category": "profile",
            "source": "Site & CV (Обо мне)",
            "url": "https://ajandris.github.io/my-public-face/",
            "title": "Профессиональный профиль Андриса Янчевскиса",
            "tags": ["профиль", "обо мне", "компетенции", "инженер", "аналитик", "ai developer"],
            "text": (
                "Андрис Янчевскис (Andris Jancevskis) — квалифицированный IT-специалист, инженер "
                "и разработчик решений на базе искусственного интеллекта (AI-driven solutions). "
                "Обладает степенью бакалавра с отличием BSc (Hons) Computing and IT (Software) "
                "от The Open University (2019) и дипломом последипломного образования Postgraduate Diploma "
                "in Computer Science with Big Data Analytics от Wrexham Glyndwr University (2023). "
                "Профессиональный бэкграунд сочетает классический системный и бизнес-анализ, глубокую "
                "экспертизу в реляционных базах данных и SQL (PostgreSQL, Oracle, MySQL), разработку бэкенда "
                "на Python (FastAPI, Django), управление проектами по стандарту PRINCE2, а также проектирование "
                "современных AI-ассистентов и RAG-систем (Retrieval-Augmented Generation). "
                "Контакты: email andris.jancevskis@gmail.com, телефон 07752 194 449, GitHub https://github.com/ajandris. "
                "Владение языками: латышский (родной), русский (свободно), английский (хороший рабочий уровень)."
            ),
        },
        {
            "id": "profile_services",
            "category": "services",
            "source": "Site (Чем я могу помочь / Услуги)",
            "url": "/#services",
            "title": "Услуги и форматы сотрудничества Андриса Янчевскиса",
            "tags": ["услуги", "сотрудничество", "разработка", "консалтинг", "ai ассистенты", "базы данных"],
            "text": (
                "Андрис Янчевскис предлагает следующие форматы прикладного сотрудничества:\n"
                "1. Прототипирование и разработка AI-ассистентов: проектирование двухэтапных архитектур на базе LLM, "
                "RAG и векторных баз данных (FAISS, Qdrant) с жесткой защитой от галлюцинаций и привязкой к источникам.\n"
                "2. Инженерия реляционных баз данных: проектирование схем данных, аудит структуры и метаданных PostgreSQL, "
                "написание и оптимизация сложных аналитических SQL-запросов, миграции и интеграции.\n"
                "3. Разработка бэкенда и веб-сервисов: создание отказоустойчивых REST API на Python с использованием "
                "FastAPI и Django, валидация через Pydantic, безопасность и контейнеризация.\n"
                "4. Системный анализ и управление IT-проектами: формализация бизнес-требований, составление спецификаций, "
                "координация команд разработчиков по методологии PRINCE2.\n"
                "Для обсуждения проекта или вакансии можно оставить контакты в чате или отправить сообщение через форму на сайте."
            ),
        },

        # ---------------- TECHNICAL SKILLS ----------------
        {
            "id": "skills_python_backend",
            "category": "skills",
            "source": "Site & CV (Навыки: Языки и бэкенд)",
            "url": "/skills",
            "title": "Навыки: Python, FastAPI, Django, REST API",
            "tags": ["python", "fastapi", "django", "rest api", "backend", "pydantic", "веб-разработка"],
            "text": (
                "Ключевой стек бэкенд-разработки Андриса Янчевскиса:\n"
                "— Python 3: глубокое понимание стандартной библиотеки, ООП, асинхронного программирования (asyncio), "
                "типизации и структур данных.\n"
                "— FastAPI: создание высокопроизводительных асинхронных REST API, интеграция Pydantic v2 схем, "
                "Dependency Injection, middleware, обработка ошибок, документация Swagger/OpenAPI.\n"
                "— Django: построение полноценных веб-приложений с использованием Django ORM, системы миграций, "
                "встроенной аутентификации, сессий, шаблонов и кастомных панелей администрирования.\n"
                "— REST API и веб-стандарты: проектирование JSON API, HTTP протокол, валидация данных, CORS, "
                "интеграция сторонних сервисов (OpenAI API, платежные шлюзы, SMTP)."
            ),
        },
        {
            "id": "skills_databases_sql",
            "category": "skills",
            "source": "Site & CV (Навыки: Базы данных и SQL)",
            "url": "/skills",
            "title": "Навыки: Базы данных SQL, PostgreSQL, Oracle, MySQL",
            "tags": ["sql", "postgresql", "oracle", "mysql", "базы данных", "dbms", "cli", "схемы данных"],
            "text": (
                "Экспертиза Андриса Янчевскиса в области баз данных и SQL:\n"
                "— СУБД: богатый многолетний практический опыт работы с PostgreSQL, Oracle Database и MySQL.\n"
                "— SQL: написание сложных аналитических запросов, агрегации, оконные функции, CTE (Common Table Expressions), "
                "соединения (JOINs), оптимизация планов выполнения (EXPLAIN ANALYZE) и индексирование.\n"
                "— Проектирование: реляционное моделирование данных, нормализация, целостность ссылок, триггеры, "
                "хранимые процедуры и системные каталоги.\n"
                "— Подтвержденный проект postgres_db_desc: специализированная CLI-утилита на чистом Python для глубокого "
                "анализа системных каталогов PostgreSQL (pg_catalog, information_schema) без внешних тяжелых зависимостей."
            ),
        },
        {
            "id": "skills_ai_rag_llm",
            "category": "skills",
            "source": "Site & CV (Навыки: AI, RAG, LLM)",
            "url": "/skills",
            "title": "Навыки: AI-агенты, RAG, LLM, FAISS, Векторный поиск",
            "tags": ["ai", "rag", "llm", "faiss", "векторный поиск", "эмбеддинги", "openai", "агенты"],
            "text": (
                "Компетенции Андриса Янчевскиса в сфере искусственного интеллекта и агентных систем:\n"
                "— RAG (Retrieval-Augmented Generation): проектирование пайплайнов индексации, чанкинга текстовых документов, "
                "генерации векторных эмбеддингов и семантического поиска.\n"
                "— Векторные базы данных: практическая работа с библиотекой FAISS (IndexFlatIP, IndexFlatL2), косинусное сходство, "
                "нормализация векторов, сохранение и загрузка индексов на диск; концептуальное понимание Qdrant.\n"
                "— LLM и промпт-инжиниринг: интеграция OpenAI API (GPT-4o, GPT-4o-mini, text-embedding-3-small), "
                "разработка специализированных системных промптов, ролевых инструкций, двухэтапных цепочек рассуждений "
                "и стратегий предотвращения галлюцинаций.\n"
                "— AI Tools & Platforms: опыт применения Antigravity, Google AI Studio, Codex, ChatGPT, Gemini."
            ),
        },
        {
            "id": "skills_frontend_web",
            "category": "skills",
            "source": "Site & CV (Навыки: Веб-разработка)",
            "url": "/skills",
            "title": "Навыки: Frontend, HTML5, CSS3, JavaScript",
            "tags": ["html", "css", "javascript", "frontend", "адаптивная верстка", "ui/ux", "web standards"],
            "text": (
                "Фронтенд-навыки Андриса Янчевскиса:\n"
                "— HTML5 и семантическая верстка: следование стандартам доступности (WAI-ARIA, доступность для клавиатуры), "
                "чистая структура документов, SEO-оптимизация и мета-теги.\n"
                "— CSS3: адаптивная и респонсивная верстка (Flexbox, CSS Grid), CSS Custom Properties (переменные), "
                "микро-анимации, медиа-запросы, кроссбраузерная совместимость, современные темные и светлые темы.\n"
                "— JavaScript: чистый нативный ES6+ (Vanilla JS) без избыточных тяжелых фреймворков для максимальной "
                "скорости и легкости: асинхронные запросы Fetch API, работа с DOM, обработка событий, доступность UI."
            ),
        },
        {
            "id": "skills_analysis_management",
            "category": "skills",
            "source": "Site & CV (Навыки: Системный анализ и управление)",
            "url": "/skills",
            "title": "Навыки: Системный анализ, PRINCE2, Управление проектами",
            "tags": ["системный анализ", "бизнес анализ", "prince2", "управление проектами", "bi", "логистика"],
            "text": (
                "Аналитические и управленческие компетенции Андриса Янчевскиса:\n"
                "— Системный и бизнес-анализ: обследование и моделирование бизнес-процессов, сбор и структурирование "
                "функциональных и нефункциональных требований, разработка технических заданий и документации.\n"
                "— Управление проектами по PRINCE2: сертифицированный PRINCE2 Practitioner (2014); планирование этапов, "
                "управление рисками, контроль качества, координация кросс-функциональных команд.\n"
                "— Business Intelligence и отчетность: анализ данных, проектирование аналитических витрин и отчетов.\n"
                "— Складская логистика и процессы: практическое знание процессов DotCom, Inbound, Inventory, Despatch "
                "и складских систем управления (Knapp WMS)."
            ),
        },

        # ---------------- GITHUB PROJECTS ----------------
        {
            "id": "project_thedecisionpoint",
            "category": "projects",
            "source": "GitHub (ajandris/TheDecisionPoint)",
            "url": "https://github.com/ajandris/TheDecisionPoint",
            "title": "Проект TheDecisionPoint: Платформа Decision Intelligence на базе AI",
            "tags": ["thedecisionpoint", "ai", "github", "decision intelligence", "swot", "матрица решений"],
            "text": (
                "Репозиторий: https://github.com/ajandris/TheDecisionPoint\n"
                "TheDecisionPoint — интеллектуальная веб-платформа для поддержки принятия сложных решений на базе AI "
                "(AI-Powered Decision Intelligence Platform). Позволяет сопоставлять альтернативные варианты, оценивать "
                "взвешенные плюсы и минусы (pros & cons), строить многокритериальные матрицы принятия решений и "
                "автоматически генерировать SWOT-анализ с высокой точностью при помощи AI. "
                "Проект демонстрирует навыки архитектурного проектирования AI-систем, интеграции LLM и "
                "создания интерактивного пользовательского интерфейса."
            ),
        },
        {
            "id": "project_postgres_db_desc",
            "category": "projects",
            "source": "GitHub (ajandris/postgres_db_desc)",
            "url": "https://github.com/ajandris/postgres_db_desc",
            "title": "Проект postgres_db_desc: CLI-утилита для интроспекции PostgreSQL",
            "tags": ["postgres_db_desc", "postgresql", "python", "cli", "sql", "github", "интроспекция"],
            "text": (
                "Репозиторий: https://github.com/ajandris/postgres_db_desc\n"
                "Консольная утилита (CLI), разработанная на чистом Python для детального описания и документирования "
                "структуры баз данных PostgreSQL. Программа извлекает метаданные (таблицы, столбцы, типы данных, "
                "первичные и внешние ключи, индексы, ограничения) напрямую из внутренних системных каталогов СУБД "
                "(pg_catalog, information_schema). Проект подтверждает экспертное владение внутренним устройством "
                "PostgreSQL и написанием надежных системных утилит на Python."
            ),
        },
        {
            "id": "project_candlemania",
            "category": "projects",
            "source": "GitHub (ajandris/candlemania)",
            "url": "https://github.com/ajandris/candlemania",
            "title": "Проект candlemania: Полнофункциональное Django веб-приложение",
            "tags": ["candlemania", "django", "python", "веб-приложение", "github", "orm"],
            "text": (
                "Репозиторий: https://github.com/ajandris/candlemania\n"
                "Веб-сайт: https://www.candlemania.p.jancevskis.com/\n"
                "Полнофункциональное веб-приложение на стеке Python и Django. Включает структурированный каталог товаров, "
                "продуманную реляционную архитектуру моделей данных, систему управления правами доступа пользователей, "
                "аутентификацию и кастомный адаптивный интерфейс. Демонстрирует глубокое понимание фреймворка Django, "
                "ORM-запросов и шаблонизации."
            ),
        },
        {
            "id": "project_simpleshop",
            "category": "projects",
            "source": "GitHub (ajandris/simpleshop)",
            "url": "https://github.com/ajandris/simpleshop",
            "title": "Проект simpleshop: Интернет-магазин на Python и Django",
            "tags": ["simpleshop", "django", "python", "e-commerce", "интернет магазин", "github"],
            "text": (
                "Репозиторий: https://github.com/ajandris/simpleshop\n"
                "Веб-сайт: https://theoldechristmasmarket.p.jancevskis.com/\n"
                "Веб-приложение интернет-магазина (E-commerce) на стеке Python и Django. "
                "Реализованы: каталог продукции, динамическая корзина покупок, оформление заказов, "
                "управление статусами заказов и интеграция с платежной системой. Подтверждает навыки разработки "
                "коммерческих транзакционных веб-сервисов на Python."
            ),
        },
        {
            "id": "project_my_public_face",
            "category": "projects",
            "source": "GitHub (ajandris/my-public-face)",
            "url": "https://github.com/ajandris/my-public-face",
            "title": "Проект my-public-face: Персональная веб-страница на веб-стандартах",
            "tags": ["my-public-face", "html", "css", "javascript", "github"],
            "text": (
                "Репозиторий: https://github.com/ajandris/my-public-face\n"
                "Веб-сайт: https://ajandris.github.io/my-public-face/\n"
                "Персональная веб-страница, спроектированная и запрограммированная на чистом HTML5, CSS3 и JavaScript. "
                "Демонстрирует базовые принципы семантической верстки, модульной организации стилей, адаптивности "
                "и соблюдения стандартов W3C."
            ),
        },
        {
            "id": "project_tic_tac_toe",
            "category": "projects",
            "source": "GitHub (ajandris/tic-tac-toe)",
            "url": "https://github.com/ajandris/tic-tac-toe",
            "title": "Проект tic-tac-toe: Интерактивная игра на нативном JavaScript",
            "tags": ["tic-tac-toe", "крестики-нолики", "javascript", "css", "github"],
            "text": (
                "Репозиторий: https://github.com/ajandris/tic-tac-toe\n"
                "Веб-сайт: https://ajandris.github.io/tic-tac-toe/\n"
                "Интерактивная браузерная игра «Крестики-нолики», реализованная на чистом нативном JavaScript (Vanilla JS). "
                "Отражает логику управления состоянием игры, проверку победных комбинаций, обработку пользовательских "
                "событий и стилизацию интерфейса на CSS."
            ),
        },
        {
            "id": "project_andris_ai_assistant",
            "category": "projects",
            "source": "GitHub (ajandris/andris-ai-personal-assistant)",
            "url": "https://github.com/ajandris/andris-ai-personal-assistant",
            "title": "Проект andris-ai-personal-assistant: Персональный сайт и AI Sales Agent",
            "tags": ["ai assistant", "sales agent", "fastapi", "faiss", "rag", "openai", "github"],
            "text": (
                "Репозиторий: https://github.com/ajandris/andris-ai-personal-assistant\n"
                "Комплексный веб-проект на базе FastAPI, Jinja2, OpenAI API и векторного хранилища FAISS. "
                "Включает полнофункционального Sales AI-агента для сравнения требований заказчика или рекрутера с "
                "подтвержденными компетенциями Андриса, сбора лидов и автоматической отправки уведомлений на почту "
                "через SMTP, а также валидацию данных, SQLite хранилище и автоматизированные тесты pytest."
            ),
        },
        {
            "id": "project_other_github_repos",
            "category": "projects",
            "source": "GitHub (ajandris профиль)",
            "url": "https://github.com/ajandris",
            "title": "Дополнительные репозитории на GitHub: django-webstart, dublin-photos, love-math",
            "tags": ["django-webstart", "dublin-photos", "docker", "javascript", "github"],
            "text": (
                "Дополнительные публичные репозитории в профиле https://github.com/ajandris:\n"
                "— django-webstart: стартовый шаблон (boilerplate) на Django с преднастроенной авторизацией и структурой.\n"
                "— dublin-photos: веб-проект с Dockerfile для контейнеризации приложения.\n"
                "— love-math, arrow-functions, personal-task-manager: практические учебные и прикладные проекты по JavaScript, "
                "алгоритмам и управлению задачами."
            ),
        },

        # ---------------- WORK EXPERIENCE ----------------
        {
            "id": "experience_boots_alliance",
            "category": "experience",
            "source": "Site & CV (Опыт работы: Boots Alliance)",
            "url": "/experience",
            "title": "Опыт работы: Boots Alliance — Burton Service Centre (2013 — по наст. время)",
            "tags": ["boots alliance", "логистика", "wms", "dotcom", "inventory", "despatch", "опыт работы"],
            "text": (
                "Компания: Boots Alliance — Burton Service Centre (Великобритания)\n"
                "Период: Ноябрь 2013 — по настоящее время (Текущая деятельность).\n"
                "Должность: Сотрудник логистического центра (Warehouse Operative).\n"
                "Ключевые направления: DotCom Inbound, Inventory Management (управление запасами), Despatch (отгрузка).\n"
                "Практический опыт: работа в крупном высоконагруженном логистическом хабе, знание принципов движения "
                "товаропотоков, инвентаризации, обработки интернет-заказов и использования складских информационных "
                "систем (Knapp WMS). Сертифицирован по складским операциям (NCFE Level 2)."
            ),
        },
        {
            "id": "experience_construction_leadership",
            "category": "experience",
            "source": "Site & CV (Опыт работы: Предпринимательство и руководство)",
            "url": "/experience",
            "title": "Опыт работы: Частная предпринимательская деятельность (2011 — 2013)",
            "tags": ["руководство командой", "строительство", "менеджмент", "планирование", "опыт работы"],
            "text": (
                "Сфера: Частная предпринимательская деятельность в строительной сфере\n"
                "Период: Ноябрь 2011 — Июль 2013.\n"
                "Роль: Руководитель бригады из 10 специалистов (наружное утепление и фасадная отделка).\n"
                "Обязанности: организация производственных процессов, планирование сроков и материально-технического "
                "обеспечения, распределение задач в бригаде, контроль стандартов качества и техники безопасности, "
                "взаимодействие с заказчиками. Подтверждает сильные лидерские и организаторские качества."
            ),
        },
        {
            "id": "experience_latvia_it_summary",
            "category": "experience",
            "source": "Site & CV (Опыт работы: IT-деятельность в Латвии 1995-2011)",
            "url": "/experience",
            "title": "Опыт работы: Системный анализ, IT-проекты и СУБД в Латвии (1995 — 2011)",
            "tags": ["латвия", "системный анализ", "бизнес анализ", "oracle", "sql", "tietoenator", "data pro", "vsaa", "вид"],
            "text": (
                "Период: Сентябрь 1995 — Август 2011 (16 лет опыта в IT-индустрии Латвии).\n"
                "Послужной список по должностям и организациям:\n"
                "1. 2011 — 2011: Старший специалист группы внедрения (Senior Specialist, Implementation Unit) — "
                "Служба государственных доходов Латвии (State Revenue Service / VID).\n"
                "2. 2009 — 2009: Бизнес- и системный аналитик (Business & Systems Analyst) — "
                "Государственное агентство социального страхования Латвии (VSAA).\n"
                "3. 2006 — 2009: Менеджер по продажам решений Business Intelligence — Data Pro, Латвия.\n"
                "4. 2005 — 2006: Руководитель проектов (Project Manager) — Data Pro, Латвия.\n"
                "5. 2003 — 2005: Системный аналитик (Systems Analyst) — DIGLAT SIA, Латвия.\n"
                "6. 1999 — 2002: Системный аналитик (Systems Analyst) — TietoEnator Financial Solutions, Латвия.\n"
                "7. 1997 — 1999: Программист и системный аналитик (Programmer & Systems Analyst) — VR Parks SIA, Латвия.\n"
                "8. 1995 — 1997: Специалист поддержки пользователей складской системы (Stock management user support) — Lattelekom SIA, Латвия."
            ),
        },

        # ---------------- EDUCATION & CERTIFICATES ----------------
        {
            "id": "edu_academic_degrees",
            "category": "education",
            "source": "Site & CV (Высшее образование)",
            "url": "/education",
            "title": "Высшее образование: The Open University (BSc Hons) и Wrexham Glyndwr University (PgDip)",
            "tags": ["образование", "bsc", "open university", "wrexham glyndwr", "big data", "computer science"],
            "text": (
                "Академические дипломы Андриса Янчевскиса:\n"
                "— 2023: Postgraduate Diploma in Computer Science with Big Data Analytics — Wrexham Glyndwr University "
                "(Последипломное образование в области компьютерных наук и аналитики больших данных).\n"
                "— 2019: BSc (Hons) Computing and IT (Software) — The Open University "
                "(Степень бакалавра с отличием по направлению «Вычислительные системы и информационные технологии / Программное обеспечение»)."
            ),
        },
        {
            "id": "edu_ai_web_training",
            "category": "education",
            "source": "Site & CV (AI и веб-обучение 2026)",
            "url": "/education",
            "title": "Программы обучения и сертификации: AI, ML, Веб-разработка (2026)",
            "tags": ["ai agents", "ai/ml", "vibe coding", "google ai", "code institute", "coursera", "сертификаты"],
            "text": (
                "Актуальные программы обучения и профессиональные дипломы (2026):\n"
                "— AI Agents Developer — AI Institute (Текущее обучение: проектирование автономных агентов, RAG, цепочки рассуждений, мультиагентные системы).\n"
                "— AI/ML Developer — AI Institute (Текущее обучение: алгоритмы машинного обучения, нейросетевые модели, обработка данных).\n"
                "— Vibe Coding — univerus.ai (Текущее обучение: передовые AI-ассистированные методы создания ПО).\n"
                "— Google AI Professional — Coursera (2026, профессиональная сертификация Google в области AI).\n"
                "— Level 5 Diploma in Web Application Development — Code Institute (2026, диплом 5 уровня по разработке веб-приложений).\n"
                "— PRINCE2 Practitioner — AXELOS / APMG (2014, международный сертификат практического управления проектами).\n"
                "— Principles of Team Leading & Warehousing (NCFE Level 2, 2016, 2019)."
            ),
        },

        # ---------------- COMPARISON & SALES MATCHING ----------------
        {
            "id": "sales_matching_guidelines",
            "category": "skills",
            "source": "Sales Agent System Rules",
            "url": "/ai-assistant",
            "title": "Сравнение требований заказчика с профилем Андриса Янчевскиса",
            "tags": ["sales agent", "сравнение", "вакансия", "требования", "матчинг", "лиды"],
            "text": (
                "Правила сопоставления требований посетителя/работодателя с профилем Андриса:\n"
                "1. Точные совпадения (Direct Matches): Python, FastAPI, Django, PostgreSQL, SQL, базы данных, "
                "RAG, FAISS, векторный поиск, OpenAI API, системный анализ, проектирование архитектуры, PRINCE2, "
                "HTML/CSS/JS, складская логистика и WMS.\n"
                "2. Смежные и усиливающие стороны (Adjacent Strengths): сильный аналитический и математический бэкграунд, "
                "диплом в Big Data Analytics, опыт руководства людьми и проектами, системная дисциплина.\n"
                "3. Честные ограничения (Transparent Limitations): если заказчик ищет узкоспециализированные технологии, "
                "которых нет в профиле (например, Swift/iOS, C++, Rust, Kubernetes на уровне DevOps-архитектора), "
                "агент обязан прямо заявить об этом, не пытаясь придумывать несуществующий опыт.\n"
                "4. Сбор контактов: при любом заинтересованном запросе предложить посетителю оставить контактные данные "
                "(имя, email, телефон/telegram, описание задачи), чтобы Андрис мог лично связаться для обсуждения деталей."
            ),
        },
    ]
    return docs


def generate_embeddings_and_build_index():
    """Generate OpenAI embeddings for all knowledge chunks and save to FAISS store."""
    print("1. Assembling knowledge documents...")
    docs = get_raw_knowledge_documents()
    print(f"Total knowledge documents: {len(docs)}")

    # Ensure directories exist
    raw_dir = ROOT_DIR / "knowledge_base" / "raw"
    processed_dir = ROOT_DIR / "knowledge_base" / "processed"
    rag_dir = ROOT_DIR / "rag"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    rag_dir.mkdir(parents=True, exist_ok=True)

    # Save raw documents
    raw_file = raw_dir / "documents.json"
    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    print(f"Saved raw documents to {raw_file}")

    # Generate embeddings with OpenAI
    api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured in .env or environment")

    client = OpenAI(api_key=api_key)
    embedding_model = settings.effective_embedding_model
    print(f"2. Generating embeddings using OpenAI model: {embedding_model}...")

    texts_to_embed = [
        f"{doc['title']}\nКатегория: {doc['category']}\nТеги: {', '.join(doc['tags'])}\n{doc['text']}"
        for doc in docs
    ]

    response = client.embeddings.create(
        input=texts_to_embed,
        model=embedding_model,
    )

    embeddings = [item.embedding for item in response.data]
    dim = len(embeddings[0])
    print(f"Generated {len(embeddings)} vectors with dimension {dim}")

    # Build FAISS store
    print(f"3. Building FAISS index (dimension={dim}, metric=cosine)...")
    store = FAISSVectorStore(dimension=dim, metric="cosine")
    store.add(vectors=embeddings, documents=docs)

    # Save to rag directory
    print(f"4. Saving FAISS index to {rag_dir}...")
    store.save(rag_dir)

    # Also save a copy to knowledge_base/processed for archival
    store.save(processed_dir)
    print(f"Successfully saved FAISS index with {store.count()} chunks in {rag_dir}")

    # Run verification test search
    print("5. Running sanity test search...")
    test_queries = [
        "Нужен разработчик на Python и FastAPI для создания RAG AI ассистента",
        "Ищем аналитика баз данных со знанием PostgreSQL и SQL",
        "Есть ли опыт в электронной коммерции на Django?",
        "Какое образование и дипломы у Андриса?",
    ]
    for q in test_queries:
        q_emb = client.embeddings.create(input=q, model=embedding_model).data[0].embedding
        hits = store.search(q_emb, top_k=2)
        try:
            print(f"\nQuery: '{q}'")
            for i, hit in enumerate(hits, 1):
                print(f"  [{i}] (Score: {hit['score']:.4f}) {hit['title']} ({hit['source']})")
        except UnicodeEncodeError:
            print(f"\nQuery: [unicode query]")
            for i, hit in enumerate(hits, 1):
                print(f"  [{i}] (Score: {hit['score']:.4f}) {hit['id']}")

    print("\nKnowledge base build completed successfully!")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    generate_embeddings_and_build_index()
