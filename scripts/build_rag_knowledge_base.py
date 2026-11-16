"""Заранее строит индекс FAISS для чата сайта из редактируемой базы знаний.

Сайт строит индекс сам при первом вопросе, но на сервере удобнее сделать это
при развёртывании: первый посетитель не ждёт создания эмбеддингов.

Индекс строится ядром app/rag/assistant_core.py с настройками лучшего варианта
(AssistantConfig по умолчанию) из файла knowledge_base/rag_a_v3/records.jsonl
и сохраняется в rag/index_rag_a_v3. Если база и настройки не менялись, индекс
повторно не строится.

Запуск (из корня проекта, ключ OPENAI_API_KEY — в .env):
    python scripts/build_rag_knowledge_base.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.services.sales_agent import SalesAgentService  # noqa: E402


def main(service: SalesAgentService | None = None) -> int:
    """Строит или загружает индекс и печатает, сколько фрагментов в нём."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    service = service or SalesAgentService()
    knowledge = service.knowledge(service._get_openai_client())
    print(f"База знаний: {service.records_path}")
    print(f"Индекс: {service.index_dir} — фрагментов: {knowledge['index'].ntotal}")
    print(f"Ключевых слов в таблице: {len(knowledge['keywords'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
