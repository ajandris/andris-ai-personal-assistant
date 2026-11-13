"""Формирует корпус RAG B парсингом страниц запущенного сайта.

Запуск (сайт должен быть запущен):
    python scripts/build_rag_b.py                  # B1: только страницы → knowledge_base/rag_b/
    python scripts/build_rag_b.py --include-pdfs   # B2: страницы + PDF сайта → knowledge_base/rag_b2/
    python scripts/build_rag_b.py --base-url http://127.0.0.1:8200
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from app.rag.site_parser import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_OUTPUT_PATH_B2,
    DEFAULT_PAGES,
    build_rag_b,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Формирование корпуса RAG B из страниц сайта")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="адрес запущенного сайта")
    parser.add_argument("--include-pdfs", action="store_true", help="вариант B2: добавить PDF-файлы сайта")
    parser.add_argument("--output", default=None, help="путь к файлу JSONL")
    args = parser.parse_args()
    output = args.output or str(DEFAULT_OUTPUT_PATH_B2 if args.include_pdfs else DEFAULT_OUTPUT_PATH)
    args.output = output

    records = build_rag_b(args.base_url, DEFAULT_PAGES, output, include_pdfs=args.include_pdfs)
    by_source = Counter(r["source_url"] for r in records)
    print(f"Сайт: {args.base_url}  (вариант {'B2' if args.include_pdfs else 'B1'})")
    for source in by_source:
        chars = sum(len(r["content"]) for r in records if r["source_url"] == source)
        print(f"  {source:<60} записей: {by_source[source]:>2}, символов: {chars}")
    print(f"Всего записей: {len(records)}, символов: {sum(len(r['content']) for r in records)}")
    print(f"Сохранено: {args.output}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
