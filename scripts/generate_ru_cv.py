"""Generate Russian version of Andris Jancevskis CV in PDF format."""

import sys
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def register_fonts():
    pdfmetrics.registerFont(TTFont("Arial", r"C:\Windows\Fonts\arial.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-Italic", r"C:\Windows\Fonts\ariali.ttf"))
    pdfmetrics.registerFont(TTFont("Arial-BoldItalic", r"C:\Windows\Fonts\arialbi.ttf"))


def build_ru_cv_pdf(output_path: Path):
    register_fonts()

    # Page size A4 is 595.27 x 841.89 points
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=32,
        bottomMargin=32,
    )

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        "RunningHeader",
        fontName="Arial",
        fontSize=8.5,
        textColor=colors.HexColor("#64748b"),
        leading=11,
    )

    name_style = ParagraphStyle(
        "CandidateName",
        fontName="Arial-Bold",
        fontSize=20,
        textColor=colors.HexColor("#0f172a"),
        leading=24,
    )

    degree_style = ParagraphStyle(
        "DegreeSubtitle",
        fontName="Arial",
        fontSize=11,
        textColor=colors.HexColor("#1e3a8a"),
        leading=14,
    )

    cv_title_style = ParagraphStyle(
        "DocTitle",
        fontName="Arial-Bold",
        fontSize=12,
        textColor=colors.HexColor("#334155"),
        leading=16,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        fontName="Arial-Bold",
        fontSize=11,
        textColor=colors.HexColor("#0f2b5c"),
        leading=15,
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        "BodyText",
        fontName="Arial",
        fontSize=9.5,
        textColor=colors.HexColor("#1e293b"),
        leading=13.5,
    )

    bullet_style = ParagraphStyle(
        "BulletItem",
        fontName="Arial",
        fontSize=9.2,
        textColor=colors.HexColor("#1e293b"),
        leading=13,
        leftIndent=12,
    )

    role_title_style = ParagraphStyle(
        "RoleTitle",
        fontName="Arial-Bold",
        fontSize=9.5,
        textColor=colors.HexColor("#0f172a"),
        leading=13.5,
    )

    period_style = ParagraphStyle(
        "PeriodText",
        fontName="Arial-Bold",
        fontSize=9,
        textColor=colors.HexColor("#2563eb"),
        leading=13,
        alignment=2,  # Right aligned
    )

    story = []

    # ==========================================
    # PAGE 1
    # ==========================================

    # Running top header
    p1_header_table = Table(
        [
            [
                Paragraph("<b>АНДРИС ЯНЧЕВСКИС</b> — andris.jancevskis@gmail.com", header_style),
                Paragraph("Стр. 1 из 2", ParagraphStyle("RightH", parent=header_style, alignment=2)),
            ]
        ],
        colWidths=[400, 123],
    )
    p1_header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(p1_header_table)
    story.append(Spacer(1, 10))

    # Name and title block
    story.append(Paragraph("Андрис Янчевскис", name_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("BSc (Hons) Computing &amp; IT (The Open University)", degree_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Резюме / Curriculum Vitae", cv_title_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=6))

    # 1. Профессиональный профиль
    story.append(Paragraph("ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ", section_heading))
    profile_text = (
        "Высокомотивированный специалист с широким кругозором в области IT-систем и складской "
        "логистики. Стремится максимально реализовать накопленный практический опыт и продолжить "
        "профессиональное развитие в разработке программных решений с применением технологий "
        "искусственного интеллекта (AI Solutions)."
    )
    story.append(Paragraph(profile_text, body_style))
    story.append(Spacer(1, 6))

    # 2. Краткий опыт работы
    story.append(Paragraph("КРАТКАЯ ТРУДОВАЯ БИОГРАФИЯ", section_heading))

    boots_row = [
        Paragraph("<b>Boots Alliance — Burton Service Centre</b><br/>"
                  "<font color='#475569'>Сотрудник логистического центра (DotCom Inbound, Inventory, Despatch)</font>", role_title_style),
        Paragraph("Ноябрь 2013 — по наст. время", period_style),
    ]
    t1 = Table([boots_row], colWidths=[370, 153])
    t1.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t1)

    self_row = [
        Paragraph("<b>Частная предпринимательская деятельность: строительная сфера</b><br/>"
                  "<font color='#475569'>Руководитель бригады из 10 специалистов (наружное утепление и фасадная отделка)</font>", role_title_style),
        Paragraph("Ноябрь 2011 — Июль 2013", period_style),
    ]
    t2 = Table([self_row], colWidths=[370, 153])
    t2.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t2)

    latvia_row = [
        Paragraph("<b>IT-деятельность в Латвии</b><br/>"
                  "<font color='#475569'>Системный и бизнес-анализ, управление IT-проектами, внедрение ПО и СУБД</font>", role_title_style),
        Paragraph("Сентябрь 1995 — Август 2011", period_style),
    ]
    t3 = Table([latvia_row], colWidths=[370, 153])
    t3.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t3)
    story.append(Spacer(1, 6))

    # 3. Образование
    story.append(Paragraph("ОБРАЗОВАНИЕ", section_heading))
    education_items = [
        "<b>Vibe Coder</b> — univerus.ai <i>(Текущее обучение)</i>",
        "<b>AI/ML Developer</b> — AI Institute <i>(Текущее обучение)</i>",
        "<b>Google AI Professional</b> — Coursera <i>(2026)</i>",
        "<b>AI Agents Developer</b> — AI Institute <i>(Текущее обучение)</i>",
        "<b>Диплом 5-го уровня по разработке веб-приложений (Level 5 Diploma in Web Application Development)</b> — Code Institute <i>(Ожидание результатов итоговой оценки)</i>",
        "<b>MSc Computer Science with Big Data Analytics</b> (Квалификация: Диплом послевузовского образования / Postgraduate Diploma) — Wrexham Glyndwr University <i>(2023)</i>",
        "<b>BSc (Hons) Computing and IT (Software)</b> — The Open University <i>(2019)</i>",
        "<b>Principles of Warehousing and Storage (NCFE Level 2)</b> — North Warwickshire &amp; Hinckley College <i>(2019)</i>",
        "<b>Team Leading (NCFE Level 2)</b> — North Warwickshire &amp; Hinckley College <i>(2016)</i>",
    ]
    for item in education_items:
        story.append(Paragraph(f"• {item}", bullet_style))
        story.append(Spacer(1, 2.5))
    story.append(Spacer(1, 4))

    # 4. Повышение квалификации
    story.append(Paragraph("ПОВЫШЕНИЕ КВАЛИФИКАЦИИ / ТРЕНИНГИ", section_heading))
    story.append(Paragraph("• <b>Управление проектами по методологии PRINCE2</b> — Managing projects with PRINCE2 <i>(2014)</i>", bullet_style))
    story.append(Spacer(1, 6))

    # 5. Сертификаты
    story.append(Paragraph("СЕРТИФИКАТЫ", section_heading))
    certs = [
        "<b>Google AI Professional</b> <i>(2026)</i>",
        "<b>NCFE (NFCA) Level 2 Certificate in Warehousing and Storage</b> <i>(2019)</i>",
        "<b>NCFE (NFCA) Level 2 Certificate in Principles of Team Leading</b> <i>(2016)</i>",
        "<b>PRINCE2 Practitioner</b> <i>(2014)</i>",
    ]
    for c in certs:
        story.append(Paragraph(f"• {c}", bullet_style))
        story.append(Spacer(1, 2))

    # ==========================================
    # PAGE BREAK TO PAGE 2
    # ==========================================
    story.append(PageBreak())

    # Running header page 2
    p2_header_table = Table(
        [
            [
                Paragraph("<b>АНДРИС ЯНЧЕВСКИС</b> — andris.jancevskis@gmail.com", header_style),
                Paragraph("Стр. 2 из 2", ParagraphStyle("RightH2", parent=header_style, alignment=2)),
            ]
        ],
        colWidths=[400, 123],
    )
    p2_header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(p2_header_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("IT-ОПЫТ В ЛАТВИИ (1995 — 2011)", section_heading))
    story.append(Paragraph("Сводный перечень выполненных обязанностей и проектов:", ParagraphStyle("SubNote", parent=body_style, textColor=colors.HexColor("#475569"))))
    story.append(Spacer(1, 5))

    it_jobs = [
        ("Старший специалист группы внедрения", "Служба государственных доходов Латвии (State Revenue Service)", "2011 — 2011"),
        ("Бизнес- и системный аналитик", "Государственное агентство социального страхования Латвии (VSAA)", "2009 — 2009"),
        ("Менеджер по продажам решений Business Intelligence", "Data Pro, Латвия", "2006 — 2009"),
        ("Руководитель проектов", "Data Pro, Латвия", "2005 — 2006"),
        ("Системный аналитик", "DIGLAT SIA, Латвия", "2003 — 2005"),
        ("Системный аналитик", "TietoEnator Financial Solutions, Латвия", "1999 — 2002"),
        ("Программист и системный аналитик", "VR Parks SIA, Латвия", "1997 — 1999"),
        ("Специалист поддержки пользователей складской системы", "Lattelekom SIA, Латвия", "1995 — 1997"),
    ]

    for role, org, period in it_jobs:
        job_table = Table(
            [
                [
                    Paragraph(f"• <b>{role}</b> — {org}", bullet_style),
                    Paragraph(period, period_style),
                ]
            ],
            colWidths=[400, 123],
        )
        job_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        story.append(job_table)

    story.append(Spacer(1, 14))

    # 7. Технологии и инструменты
    story.append(Paragraph("ПРИКЛАДНЫЕ СИСТЕМЫ, ЯЗЫКИ ПРОГРАММИРОВАНИЯ И ИНСТРУМЕНТЫ", section_heading))
    tech_categories = [
        ("Разработка AI-агентов:", "LLM, RAG, архитектура агентов, контекстная память."),
        ("Инструменты AI-разработки:", "Antigravity, Codex, Google AI Studio."),
        ("Сервисы вопрос-ответ AI:", "ChatGPT, Gemini."),
        ("Стек программирования и веб:", "Python, Django, FastAPI, PHP, HTML, CSS, JavaScript, JSON, REST API."),
        ("Базы данных и СУБД:", "PostgreSQL, Oracle, MySQL, реляционное проектирование, оптимизация SQL."),
        ("Офисные и прикладные пакеты:", "MS Office (Excel, Word, PowerPoint, Outlook), MS Visio, MS Project, Knapp WMS."),
    ]
    for cat, details in tech_categories:
        story.append(Paragraph(f"• <b>{cat}</b> {details}", bullet_style))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 14))

    # 8. Языки
    story.append(Paragraph("ВЛАДЕНИЕ ЯЗЫКАМИ", section_heading))
    languages = [
        ("Латышский", "Родной (Native)"),
        ("Русский", "Свободный (Fluent)"),
        ("Английский", "Хороший / Свободный рабочий (Good working proficiency)"),
    ]
    for lang, level in languages:
        story.append(Paragraph(f"• <b>{lang}:</b> {level}", bullet_style))
        story.append(Spacer(1, 2.5))

    story.append(Spacer(1, 18))

    # 9. Рекомендации
    story.append(Paragraph("РЕКОМЕНДАЦИИ", section_heading))
    story.append(Paragraph("Предоставляются по запросу (References available upon request).", body_style))

    doc.build(story)
    print(f"Russian CV successfully created at: {output_path}")


if __name__ == "__main__":
    out = Path("media/docs/Andris Jancevskis CV September 2026 web RU.pdf")
    out.parent.mkdir(parents=True, exist_ok=True)
    build_ru_cv_pdf(out)
