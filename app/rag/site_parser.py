"""Автоматическое формирование корпуса RAG B из страниц сайта.

Корпус RAG B моделирует ситуацию «базы знаний нет, есть только сайт»: текст
берётся из опубликованных страниц без ручной обработки. Парсер намеренно простой:
- берётся только содержимое <main>; шапка, меню и подвал отбрасываются;
- удаляются скрипты, стили, иконки (svg), формы и кнопки;
- каждый блок <section> становится одной записью; заголовок записи — первый
  заголовок h1–h3 внутри секции;
- у ссылок сохраняется и видимый текст, и адрес: «GitHub (https://github.com/...)».
  Внутренние якоря (#...) и ссылки mailto:/tel: не сохраняются;
- декоративные символы и эмодзи (↗, →, ✦, 🤖 и т. п.) удаляются, строки без букв
  и цифр отбрасываются.

Вариант B2 дополнительно читает PDF-файлы, на которые ссылаются страницы сайта
(только файлы того же сайта, внешние ссылки не посещаются — как у типичных
краулеров по умолчанию). Текст извлекается без OCR: отсканированные документы
дают пустой текст. Телефоны и адреса электронной почты удаляются.

Записи RAG B имеют ту же структуру, что и записи RAG A, поэтому обрабатываются
тем же кодом (assistant_core). Они не проверялись вручную: verified=false,
verification_status="unreviewed". Загружать их нужно с require_verified=False.

Как и в assistant_core, функции используют только переданные параметры.
"""

from __future__ import annotations

import io
import json
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE_URL = "http://127.0.0.1:8200"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "knowledge_base" / "rag_b" / "records.jsonl"
DEFAULT_OUTPUT_PATH_B2 = PROJECT_ROOT / "knowledge_base" / "rag_b2" / "records.jsonl"
# Страница /ai-assistant не включается: это интерфейс чата, а не сведения о профиле.
DEFAULT_PAGES = ("/", "/experience", "/skills", "/education", "/portfolio", "/contact")

SKIP_TAGS = {"script", "style", "svg", "form", "button", "noscript", "template", "header", "footer", "nav"}
BLOCK_TAGS = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "article", "br", "tr", "td", "th", "span"}
HEADING_TAGS = {"h1", "h2", "h3"}
SKIPPED_LINK_PREFIXES = ("#", "javascript:", "mailto:", "tel:")
INVISIBLE_CHARS = {"\ufe0f", "\u200d"}  # селектор варианта эмодзи и соединитель
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+?\d[\d\s()-]{8,}\d")
VOID_TAGS = {"br", "img", "input", "meta", "link", "hr", "source", "path", "circle", "line", "rect", "polyline", "polygon"}


class _MainSectionsParser(HTMLParser):
    """Собирает текст секций внутри <main>, пропуская служебные элементы."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main = 0
        self.skip_depth = 0
        self.sections: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.heading_depth = 0
        self.heading_parts: list[str] = []
        self.link_stack: list[str | None] = []
        self.links: list[str] = []

    def _start_section(self, section_id: str) -> None:
        self.current = {"section_id": section_id, "title": "", "parts": []}
        self.sections.append(self.current)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "main":
            self.in_main += 1
            return
        if not self.in_main:
            return
        if self.skip_depth or tag in SKIP_TAGS:
            if tag not in VOID_TAGS:
                self.skip_depth += 1
            return
        if tag == "section":
            self._start_section(attributes.get("id") or f"section_{len(self.sections) + 1}")
        elif self.current is None:
            self._start_section("main")
        if tag in HEADING_TAGS and not self.current["title"]:
            self.heading_depth += 1
            self.heading_parts = []
        if tag == "a":
            href = (attributes.get("href") or "").strip()
            kept = None if not href or href.startswith(SKIPPED_LINK_PREFIXES) else href
            self.link_stack.append(kept)
            if kept:
                self.links.append(kept)
        if tag in BLOCK_TAGS:
            self.current["parts"].append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "main":
            self.in_main = max(0, self.in_main - 1)
            return
        if not self.in_main:
            return
        if self.skip_depth:
            if tag not in VOID_TAGS:
                self.skip_depth -= 1
            return
        if tag in HEADING_TAGS and self.heading_depth:
            self.heading_depth -= 1
            if self.current is not None and not self.current["title"]:
                self.current["title"] = " ".join("".join(self.heading_parts).split())
        if tag == "a" and self.link_stack:
            href = self.link_stack.pop()
            if href and self.current is not None:
                self.current["parts"].append(f" ({href})")
        if self.current is not None and tag in BLOCK_TAGS:
            self.current["parts"].append("\n")

    def handle_data(self, data: str) -> None:
        if not self.in_main or self.skip_depth or self.current is None:
            return
        self.current["parts"].append(data)
        if self.heading_depth:
            self.heading_parts.append(data)


def remove_decorative_symbols(text: str) -> str:
    """Удаляет эмодзи и декоративные символы (↗, →, ✦ и т. п.).

    Удаляются символы вне ASCII из категорий Unicode «прочие символы» (So),
    «математические символы» (Sm) и «модификаторы» (Sk). Буквы, цифры, знаки
    препинания, «•», кавычки «» и тире сохраняются.
    """
    return "".join(
        ch for ch in text
        if ch not in INVISIBLE_CHARS and not (ord(ch) > 127 and unicodedata.category(ch) in ("So", "Sm", "Sk"))
    )


def clean_text(text: str) -> str:
    """Убирает декоративные символы, схлопывает пробелы и отбрасывает строки без букв и цифр."""
    cleaned: list[str] = []
    for raw in text.splitlines():
        line = " ".join(remove_decorative_symbols(raw).split())
        if not re.search(r"\w", line):
            continue
        # Адрес ссылки, оказавшийся на отдельной строке, присоединяем к тексту ссылки.
        if cleaned and re.fullmatch(r"\(\S+\)", line):
            cleaned[-1] = f"{cleaned[-1]} {line}"
        else:
            cleaned.append(line)
    return "\n".join(cleaned)


def extract_sections(html: str) -> list[dict[str, str]]:
    """Извлекает из HTML-страницы секции <main>: идентификатор, заголовок и текст."""
    parser = _MainSectionsParser()
    parser.feed(html)
    sections = []
    for section in parser.sections:
        text = clean_text("".join(section["parts"]))
        if text:
            sections.append({"section_id": section["section_id"], "title": section["title"], "text": text})
    return sections


def extract_links(html: str) -> list[str]:
    """Возвращает адреса ссылок из <main> в порядке появления, без повторов."""
    parser = _MainSectionsParser()
    parser.feed(html)
    return list(dict.fromkeys(parser.links))


def same_site_pdf_links(links: list[str], page_url: str) -> list[str]:
    """Оставляет ссылки на PDF-файлы того же сайта и возвращает их абсолютные адреса."""
    site = urllib.parse.urlsplit(page_url).netloc
    result = []
    for link in links:
        absolute = urllib.parse.urljoin(page_url, link)
        parts = urllib.parse.urlsplit(absolute)
        if parts.netloc == site and parts.path.lower().endswith(".pdf"):
            result.append(absolute)
    return list(dict.fromkeys(result))


def remove_personal_contacts(text: str) -> str:
    """Удаляет адреса электронной почты и номера телефонов.

    Номером телефона считается последовательность из цифр, пробелов, скобок и
    дефисов, содержащая не меньше 10 цифр; поэтому периоды вида «1999 - 2002»
    не удаляются.
    """
    text = EMAIL_RE.sub("", text)
    return PHONE_RE.sub(lambda m: "" if sum(ch.isdigit() for ch in m.group()) >= 10 else m.group(), text)


def pdf_pages_text(data: bytes) -> list[str]:
    """Извлекает текст каждой страницы PDF (без OCR: у сканов текст пустой)."""
    from pypdf import PdfReader  # импорт здесь: pypdf нужен только варианту B2

    reader = PdfReader(io.BytesIO(data))
    return [page.extract_text() or "" for page in reader.pages]


def pdf_to_records(pages_text: list[str], pdf_path: str, updated_at: str | None = None) -> list[dict[str, Any]]:
    """Превращает страницы PDF в записи корпуса: одна непустая страница — одна запись."""
    name = urllib.parse.unquote(pdf_path.rsplit("/", 1)[-1])
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower().removesuffix(".pdf")).strip("_")
    records = []
    for number, raw in enumerate(pages_text, start=1):
        text = clean_text(remove_personal_contacts(raw))
        if not text:
            continue
        records.append({
            "record_id": f"rag_b_pdf_{slug}_p{number}_{number:03d}",
            "entity_type": "document_page",
            "title": f"{name}, стр. {number}",
            "content": text,
            "source_type": "site_pdf",
            "source_url": pdf_path,
            "skills": [],
            "language": "ru",
            "verification_status": "unreviewed",
            "verified": False,
            "public": True,
            "updated_at": updated_at or date.today().isoformat(),
            "site": "ru",
        })
    return records


def page_key(path: str) -> str:
    """Короткое имя страницы для идентификаторов записей: "/" → "home"."""
    key = path.strip("/").replace("/", "_").replace("-", "_")
    return key or "home"


def sections_to_records(sections: list[dict[str, str]], page_path: str, base_url: str = DEFAULT_BASE_URL,
                        updated_at: str | None = None) -> list[dict[str, Any]]:
    """Превращает секции страницы в записи корпуса RAG B (та же схема, что у RAG A)."""
    key = page_key(page_path)
    records = []
    for number, section in enumerate(sections, start=1):
        section_slug = re.sub(r"[^a-z0-9]+", "_", section["section_id"].lower()).strip("_") or f"s{number}"
        records.append({
            "record_id": f"rag_b_{key}_{section_slug}_{number:03d}",
            "entity_type": "page_section",
            "title": section["title"] or key,
            "content": section["text"],
            "source_type": "site_parse",
            "source_url": page_path,
            "skills": [],
            "language": "ru",
            "verification_status": "unreviewed",
            "verified": False,
            "public": True,
            "updated_at": updated_at or date.today().isoformat(),
            "site": "ru",
        })
    return records


def fetch_bytes(url: str, timeout: float = 15.0) -> bytes:
    """Загружает ресурс по HTTP и возвращает его содержимое."""
    request = urllib.request.Request(url, headers={"User-Agent": "rag-b-builder"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def fetch_html(url: str, timeout: float = 15.0) -> str:
    """Загружает HTML страницы по HTTP."""
    return fetch_bytes(url, timeout).decode("utf-8")


def build_rag_b(base_url: str = DEFAULT_BASE_URL, pages: tuple[str, ...] = DEFAULT_PAGES,
                output_path: str | Path = DEFAULT_OUTPUT_PATH, include_pdfs: bool = False) -> list[dict[str, Any]]:
    """Загружает страницы сайта, извлекает секции и сохраняет корпус в JSONL.

    include_pdfs=False — вариант B1 (только страницы);
    include_pdfs=True — вариант B2 (страницы и PDF-файлы того же сайта, на которые они ссылаются).
    """
    records = []
    pdf_urls: list[str] = []
    for path in pages:
        page_url = base_url.rstrip("/") + path
        html = fetch_html(page_url)
        records.extend(sections_to_records(extract_sections(html), path, base_url))
        if include_pdfs:
            pdf_urls.extend(same_site_pdf_links(extract_links(html), page_url))
    for pdf_url in dict.fromkeys(pdf_urls):
        pdf_path = urllib.parse.urlsplit(pdf_url).path
        records.extend(pdf_to_records(pdf_pages_text(fetch_bytes(pdf_url)), pdf_path))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
    return records
