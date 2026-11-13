"""Проверка корпуса Master Knowledge Base (RAG A) перед индексацией.

Запуск:
    python scripts/validate_knowledge_base.py
    python scripts/validate_knowledge_base.py knowledge_base/rag_a/records.jsonl

Что проверяется:
- каждая строка — корректный JSON и соответствует схеме KnowledgeRecord;
- record_id уникальны, содержимое записей не дублируется;
- verified согласован с verification_status;
- в тексте нет телефонов и email-адресов (персональные данные не индексируются).

В конце выводится, сколько записей будет допущено к индексации
(verified=true и public=true). Код возврата 1, если есть ошибки.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT_DIR / "knowledge_base" / "rag_a" / "records.jsonl"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\s()-]{8,}\d")

EntityType = Literal["profile", "contact", "experience", "education", "skill", "project", "service", "boundary", "faq"]
SourceType = Literal["cv", "github_profile", "github_readme", "github_code", "github_repo_meta", "site_code", "author_statement", "document", "public_web"]
# Статусы из этапа 2: Подтверждено / Сообщено автором / Требует проверки / Закрыто
Status = Literal["confirmed", "author_reported", "needs_check", "closed"]


class KnowledgeRecord(BaseModel):
    record_id: str = Field(pattern=r"^[a-z0-9_]+_\d{3}$")
    entity_type: EntityType
    title: str = Field(min_length=3)
    content: str = Field(min_length=20, max_length=1200)
    source_type: SourceType
    source_url: str = Field(min_length=1)
    skills: list[str] = []
    language: Literal["ru", "en"]
    verification_status: Status
    verified: bool
    public: bool
    updated_at: date
    # На какой версии сайта запись может использоваться: all, ru или en
    site: Literal["all", "ru", "en"] = "all"

    @field_validator("content")
    @classmethod
    def no_personal_contacts(cls, value: str) -> str:
        if EMAIL_RE.search(value) or PHONE_RE.search(value):
            raise ValueError("текст содержит email или телефон — персональные данные не индексируются")
        return value

    @model_validator(mode="after")
    def verified_matches_status(self) -> "KnowledgeRecord":
        if self.verified != (self.verification_status == "confirmed"):
            raise ValueError("verified=true допустимо только при verification_status='confirmed'")
        if self.verification_status == "closed" and self.public:
            raise ValueError("закрытая запись не может быть public=true")
        return self


def validate_file(path: Path) -> tuple[list[KnowledgeRecord], list[str]]:
    records: list[KnowledgeRecord] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_content: dict[str, str] = {}

    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = KnowledgeRecord.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValidationError) as exc:
            errors.append(f"строка {line_no}: {exc}")
            continue

        if record.record_id in seen_ids:
            errors.append(f"строка {line_no}: повторяющийся record_id {record.record_id}")
        seen_ids.add(record.record_id)

        key = " ".join(record.content.lower().split())
        if key in seen_content:
            errors.append(f"строка {line_no}: текст совпадает с записью {seen_content[key]}")
        seen_content[key] = record.record_id

        records.append(record)

    return records, errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    records, errors = validate_file(path)

    for err in errors:
        print("ОШИБКА", err)

    indexable = [r for r in records if r.verified and r.public]
    by_status: dict[str, int] = {}
    for r in records:
        by_status[r.verification_status] = by_status.get(r.verification_status, 0) + 1

    print(f"Файл: {path}")
    print(f"Записей: {len(records)}, ошибок: {len(errors)}")
    print("По статусам:", ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
    print(f"Допущено к индексации (verified и public): {len(indexable)}")
    return 1 if errors else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
