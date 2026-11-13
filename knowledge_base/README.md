# Master Knowledge Base (RAG A)

Эталонная редактируемая база знаний AI-ассистента. Структура записей соответствует разделам 6–10 документа этапа 2.

## Файлы

| Файл | Назначение |
|---|---|
| `rag_a/records.jsonl` | Корпус RAG A: одна запись — один проверяемый факт с источником |
| `../scripts/validate_knowledge_base.py` | Проверка корпуса перед индексацией |

Корпус RAG B (автоматический парсинг страниц сайта) хранится отдельно в `rag_b/records.jsonl` и не смешивается с RAG A. Он создаётся скриптом, при запущенном сайте:

```bash
python scripts/build_rag_b.py --base-url http://127.0.0.1:8200
```

Записи RAG B имеют ту же схему, но вручную не проверялись (`verified: false`, `verification_status: "unreviewed"`), поэтому ядро загружает их с `require_verified=False`. Валидатор `validate_knowledge_base.py` предназначен для RAG A. Страница `/ai-assistant` в RAG B не включается: это интерфейс чата. Вариант **RAG B2** (`rag_b2/records.jsonl`) дополнительно читает PDF-файлы того же сайта, на которые ссылаются страницы (резюме, благодарственное письмо): `python scripts/build_rag_b.py --include-pdfs`. Текст извлекается без OCR, поэтому отсканированное благодарственное письмо текста не даёт; телефоны и адреса электронной почты удаляются. Внешние ссылки (GitHub и др.) не посещаются, как у типичных краулеров по умолчанию. Парсер удаляет эмодзи и декоративные символы (↗, →, ✦) и сохраняет адреса ссылок рядом с их текстом: «GitHub (https://github.com/...)».

## Схема записи

| Поле | Значение |
|---|---|
| `record_id` | Уникальный идентификатор, например `project_simpleshop_002` |
| `entity_type` | `profile`, `contact`, `experience`, `education`, `skill`, `project`, `service`, `boundary`, `faq` |
| `title` | Короткий заголовок |
| `content` | Один законченный факт (1–3 предложения) |
| `source_type` | `cv`, `github_readme`, `github_code`, `github_repo_meta`, `github_profile`, `site_code`, `author_statement`, `document`, `public_web` |
| `source_url` | Ссылка на подтверждение |
| `skills` | Связанные технологии и компетенции |
| `language` | `ru` или `en` |
| `verification_status` | `confirmed`, `author_reported`, `needs_check`, `closed` (статусы этапа 2) |
| `verified` | `true` только при `confirmed` |
| `public` | Разрешение на публикацию |
| `updated_at` | Дата последней проверки |
| `site` | Необязательное: `all` (по умолчанию), `ru` или `en` — на какой версии сайта запись может использоваться |

В индекс попадают только записи с `verified=true` и `public=true`. Индекс каждой версии сайта строится только из записей с `site` = `all` или кодом этой версии; например, запись с `site: "ru"` не попадает в индекс английского сайта, даже если вопрос задан по-русски.

## Как редактировать

1. Измените или добавьте строку в `records.jsonl` (одна строка — одна запись в формате JSON).
2. Для нового факта от автора укажите `source_type: "author_statement"`, `verification_status: "author_reported"`, `verified: false`. После проверки поменяйте на `confirmed` и `true`.
3. Запустите проверку:

   ```bash
   python scripts/validate_knowledge_base.py
   ```

4. Пересоберите индекс.
