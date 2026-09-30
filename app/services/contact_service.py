import asyncio
import email.utils
import logging
import smtplib
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Base project directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_db_path(settings: Optional[Settings] = None) -> Path:
    """Resolve absolute path to SQLite messages database."""
    if settings is None:
        settings = get_settings()
    db_raw = Path(settings.sqlite_db_path)
    if db_raw.is_absolute():
        db_path = db_raw
    else:
        db_path = PROJECT_ROOT / db_raw
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def init_db(settings: Optional[Settings] = None) -> None:
    """Initialize SQLite database schema for messages."""
    db_path = get_db_path(settings)
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                subject TEXT,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                email_sent INTEGER DEFAULT 0
            );
            """
        )
        # Create alias view 'massages' for full compatibility
        cursor.execute(
            """
            CREATE VIEW IF NOT EXISTS massages AS SELECT * FROM messages;
            """
        )
        conn.commit()


def save_message_to_db(
    name: str,
    email_addr: str,
    subject: Optional[str],
    message: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> int:
    """Save an incoming contact message into the SQLite database."""
    init_db(settings)
    db_path = get_db_path(settings)
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO messages (name, email, subject, message, ip_address, user_agent, email_sent)
            VALUES (?, ?, ?, ?, ?, ?, 0);
            """,
            (
                name.strip(),
                email_addr.strip(),
                (subject or "").strip() or None,
                message.strip(),
                ip_address or "",
                user_agent or "",
            ),
        )
        conn.commit()
        message_id = cursor.lastrowid
        return message_id


def mark_email_sent(message_id: int, settings: Optional[Settings] = None) -> None:
    """Update email_sent flag for a saved message."""
    db_path = get_db_path(settings)
    with sqlite3.connect(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET email_sent = 1 WHERE id = ?;",
            (message_id,),
        )
        conn.commit()


def get_all_messages(settings: Optional[Settings] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Retrieve messages from database for inspection or admin purposes."""
    init_db(settings)
    db_path = get_db_path(settings)
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages ORDER BY id DESC LIMIT ?;",
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


async def verify_recaptcha(
    token: Optional[str],
    ip_address: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> bool:
    """Verify Google reCAPTCHA token if secret key is configured."""
    if settings is None:
        settings = get_settings()

    secret_key = settings.recaptcha_secret_key.strip()
    # If reCAPTCHA is not configured, bypass verification safely for local dev & testing
    if not secret_key:
        return True

    if not token or not token.strip():
        logger.warning("reCAPTCHA token missing while secret key is configured")
        return False

    url = "https://www.google.com/recaptcha/api/siteverify"
    data = {
        "secret": secret_key,
        "response": token.strip(),
    }
    if ip_address:
        data["remoteip"] = ip_address

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, data=data)
            resp.raise_for_status()
            result = resp.json()
            success = bool(result.get("success", False))
            if not success:
                logger.warning("reCAPTCHA verification failed: %s", result.get("error-codes"))
            return success
    except Exception as exc:
        logger.error("Error communicating with reCAPTCHA service: %s", exc)
        return False

def _send_mime_message(
    from_email: str,
    to_email: str,
    msg: MIMEMultipart,
    settings: Settings,
) -> bool:
    """Helper to dispatch a MIME message through configured SMTP server."""
    host = settings.smtp_host.strip()
    if not host:
        logger.info("SMTP host not configured. Skipping email dispatch.")
        return False

    port = settings.smtp_port
    user = settings.smtp_user.strip()
    password = settings.smtp_password

    try:
        # Port 465 is standard SMTPS (SSL); port 587 is submission (STARTTLS)
        use_ssl = settings.smtp_use_ssl and port != 587
        use_tls = settings.smtp_use_tls or port == 587

        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if use_tls:
                server.starttls()

        if user and password:
            server.login(user, password)

        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        logger.info("Successfully sent email via SMTP to %s", to_email)
        return True
    except Exception as exc:
        logger.error("Failed to send email via SMTP to %s: %s", to_email, exc)
        return False


def send_smtp_email_sync(
    name: str,
    email_addr: str,
    subject: Optional[str],
    message: str,
    settings: Optional[Settings] = None,
) -> bool:
    """Synchronously send an admin notification email via configured SMTP server."""
    if settings is None:
        settings = get_settings()

    host = settings.smtp_host.strip()
    if not host:
        logger.info("SMTP host not configured. Skipping email dispatch.")
        return False

    user = settings.smtp_user.strip()
    from_email = settings.smtp_from_email.strip() or user or "noreply@andris.jancevskis.com"
    to_email = settings.smtp_to_email.strip() or user or from_email

    subj_text = f"[Сайт] {subject.strip()}" if subject and subject.strip() else f"[Сайт] Новое сообщение от {name}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj_text
    msg["From"] = email.utils.formataddr((name, from_email))
    msg["To"] = to_email
    msg["Reply-To"] = email_addr
    msg["Date"] = email.utils.formatdate(localtime=True)

    plain_text = (
        f"Новое сообщение с формы контактов персонального сайта:\n\n"
        f"Имя: {name}\n"
        f"Email: {email_addr}\n"
        f"Тема: {subject or 'Без темы'}\n\n"
        f"Сообщение:\n{message}\n"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #1f2937; padding: 20px;">
      <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 8px; padding: 24px; background: #ffffff;">
        <h2 style="color: #1e3a8a; margin-top: 0;">Новое сообщение с сайта</h2>
        <p><strong>Отправитель:</strong> {name}</p>
        <p><strong>Email для ответа:</strong> <a href="mailto:{email_addr}">{email_addr}</a></p>
        <p><strong>Тема:</strong> {subject or 'Без темы'}</p>
        <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
        <p><strong>Сообщение:</strong></p>
        <div style="background: #f8fafc; padding: 16px; border-radius: 6px; border: 1px solid #e2e8f0; white-space: pre-wrap;">{message}</div>
      </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    return _send_mime_message(from_email, to_email, msg, settings)


def send_acknowledgement_email_sync(
    name: str,
    email_addr: str,
    subject: str,
    message: str,
    settings: Optional[Settings] = None,
) -> bool:
    """Synchronously send an automated acknowledgement receipt email to the sender."""
    if settings is None:
        settings = get_settings()

    host = settings.smtp_host.strip()
    if not host or not email_addr:
        return False

    user = settings.smtp_user.strip()
    from_email = settings.smtp_from_email.strip() or user or "noreply@andris.jancevskis.com"
    app_name = "Андрис Янчевскис"

    clean_subj = subject.strip() if subject else "Обращение с сайта"
    subj_text = f"Подтверждение получения: {clean_subj}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subj_text
    msg["From"] = email.utils.formataddr((app_name, from_email))
    msg["To"] = email.utils.formataddr((name, email_addr))
    reply_to = settings.smtp_to_email.strip() or from_email
    msg["Reply-To"] = reply_to
    msg["Date"] = email.utils.formatdate(localtime=True)

    plain_text = (
        f"Здравствуйте, {name}!\n\n"
        f"Ваше сообщение успешно получено и зарегистрировано в системе.\n\n"
        f"Тема: {clean_subj}\n"
        f"Дата: {email.utils.formatdate(localtime=True)}\n\n"
        f"Копия вашего обращения:\n"
        f"----------------------------------------\n"
        f"{message}\n"
        f"----------------------------------------\n\n"
        f"Благодарю за обращение! Я ознакомлюсь с материалами и свяжусь с вами в ближайшее время.\n\n"
        f"С уважением,\n"
        f"Андрис Янчевскис\n"
        f"Персональный сайт с AI-ассистентом\n"
    )

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin: 0; padding: 24px; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #f8fafc;">
      <div style="max-width: 600px; margin: 0 auto; background-color: #111827; border: 1px solid #1e293b; border-radius: 14px; padding: 32px; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);">
        <div style="border-bottom: 1px solid #1f293d; padding-bottom: 20px; margin-bottom: 24px;">
          <span style="color: #38bdf8; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;">Подтверждение получения</span>
          <h1 style="color: #ffffff; font-size: 22px; margin: 8px 0 0 0; font-weight: 700;">Ваше сообщение успешно принято</h1>
        </div>
        <p style="font-size: 16px; line-height: 1.6; color: #e2e8f0; margin-top: 0;">Здравствуйте, <strong>{name}</strong>!</p>
        <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1;">Благодарю за проявленный интерес. Ваше сообщение по теме <strong>«{clean_subj}»</strong> получено. Я ознакомлюсь с ним и свяжусь с вами в ближайшее время по указанному адресу электронной почты.</p>
        <div style="background-color: #162032; border: 1px solid #243247; border-radius: 10px; padding: 20px; margin: 24px 0;">
          <p style="margin: 0 0 10px 0; font-size: 13px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em;">Копия вашего обращения</p>
          <div style="color: #f1f5f9; font-size: 14px; line-height: 1.6; white-space: pre-wrap;">{message}</div>
        </div>
        <div style="border-top: 1px solid #1f293d; padding-top: 20px; margin-top: 24px; color: #94a3b8; font-size: 13px; line-height: 1.6;">
          <strong style="color: #e2e8f0;">Андрис Янчевскис</strong><br>
          Персональный сайт с AI-ассистентом для демонстрации компетенций
        </div>
      </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

    return _send_mime_message(from_email, email_addr, msg, settings)


async def send_smtp_email_async(
    name: str,
    email_addr: str,
    subject: Optional[str],
    message: str,
    settings: Optional[Settings] = None,
) -> bool:
    """Asynchronously execute admin notification email dispatch using thread pool."""
    return await asyncio.to_thread(
        send_smtp_email_sync, name, email_addr, subject, message, settings
    )


async def send_acknowledgement_email_async(
    name: str,
    email_addr: str,
    subject: str,
    message: str,
    settings: Optional[Settings] = None,
) -> bool:
    """Asynchronously execute sender acknowledgement email dispatch using thread pool."""
    return await asyncio.to_thread(
        send_acknowledgement_email_sync, name, email_addr, subject, message, settings
    )
