from __future__ import annotations

import email
import html
import imaplib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email import utils as email_utils
from email.header import decode_header
from typing import Any

import requests

TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
IMAP_SERVER = "outlook.live.com"
IMAP_PORT = 993
DEFAULT_MAILBOXES = ("INBOX", "Junk")
CODE_RE = re.compile(r"(?<![A-Za-z0-9])([A-Z0-9]{4,10})(?![A-Za-z0-9])", re.I)
DIGIT_CODE_RE = re.compile(r"(?<![\d/.-])(\d{4,8})(?![\d/.-])")


@dataclass(slots=True)
class AccountInput:
    email: str
    password: str
    client_id: str
    refresh_token: str


@dataclass(slots=True)
class MailItem:
    mailbox: str
    uid: str
    subject: str
    sender: str
    to: str
    date: str
    timestamp: float
    codes: list[str]
    preview: str


def parse_combo(combo: str) -> AccountInput:
    """Parse: email----password----client_id----refresh_token.

    Password is accepted for compatibility with account exports, but OAuth IMAP uses
    refresh_token + client_id; the password is not sent anywhere by this tool.
    """
    parts = [p.strip() for p in (combo or "").strip().split("----", 3)]
    if len(parts) != 4 or "@" not in parts[0] or not parts[2] or not parts[3]:
        raise ValueError("格式应为：邮箱----密码----client_id----refresh_token")
    return AccountInput(parts[0], parts[1], parts[2], parts[3])


def decode_header_value(value: str | None) -> str:
    if not value:
        return ""
    chunks: list[str] = []
    try:
        for part, charset in decode_header(str(value)):
            if isinstance(part, bytes):
                try:
                    chunks.append(part.decode(charset or "utf-8", "replace"))
                except LookupError:
                    chunks.append(part.decode("utf-8", "replace"))
            else:
                chunks.append(str(part))
        return "".join(chunks)
    except Exception:
        return str(value)


def fetch_access_token(client_id: str, refresh_token: str, timeout: int = 25) -> tuple[str, str | None]:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": "https://outlook.office.com/IMAP.AccessAsUser.All offline_access",
        },
        timeout=timeout,
    )
    if resp.status_code != 200:
        detail = resp.text[:800]
        raise RuntimeError(f"获取 access_token 失败：HTTP {resp.status_code} {detail}")
    data = resp.json()
    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError(data.get("error_description") or "Token 响应中没有 access_token")
    return access_token, data.get("refresh_token")


def _html_to_text(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", value)
    value = re.sub(r"(?i)<br\s*/?>", "\n", value)
    value = re.sub(r"(?i)</p>", "\n", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"[ \t\r\f\v]+", " ", value).strip()


def extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        html_body = ""
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "").lower()
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, "replace")
            if ctype == "text/plain":
                return text.strip()
            if ctype == "text/html" and not html_body:
                html_body = _html_to_text(text)
        return html_body.strip()
    payload = msg.get_payload(decode=True)
    if payload:
        return payload.decode(msg.get_content_charset() or "utf-8", "replace").strip()
    return str(msg.get_payload() or "").strip()


def extract_codes(text: str) -> list[str]:
    """Prefer likely numeric OTPs; include alphanumeric fallback only when needed."""
    source = text or ""
    result: list[str] = []
    keywords = ("code", "验证码", "verification", "verify", "security", "login", "一次性", "temporary", "otp", "passcode")
    for match in DIGIT_CODE_RE.finditer(source):
        code = match.group(1)
        start, end = match.span(1)
        before = source[max(0, start - 80): start].lower()
        after = source[end: min(len(source), end + 24)].lower()
        ctx = before + after
        # Drop obvious dates/times/prices/plan numbers before ranking.
        if (code.startswith(("19", "20")) and len(code) == 4) or re.search(r"^\s*[-/年月日:]", after) or any(token in before[-24:] for token in ("date", "日期", "时间", "time")):
            continue
        if any(word in ctx for word in keywords):
            if code not in result:
                result.append(code)
    if result:
        return sorted(result, key=lambda c: (0 if 5 <= len(c) <= 6 else 1, len(c)))[:10]
    for match in re.finditer(r"(?<!\d)(\d{4,8})(?!\d)", source):
        code = match.group(1)
        start, end = match.span(1)
        before = source[max(0, start - 24): start].lower()
        after = source[end: min(len(source), end + 8)].lower()
        if (code.startswith(("19", "20")) and len(code) == 4) or re.search(r"^\s*[-/年月日:]", after) or any(token in before for token in ("date", "日期", "时间", "time")):
            continue
        if code not in result:
            result.append(code)
    if result:
        return sorted(result, key=lambda c: (0 if 5 <= len(c) <= 6 else 1, len(c)))[:10]
    # Alphanumeric fallback, ignore common words.
    stop = {"HTTP", "HTML", "FROM", "DATE", "CODE", "LOGIN", "EMAIL", "OUTLOOK", "MICROSOFT"}
    for code in CODE_RE.findall(source):
        c = code.upper()
        if c in stop or c.isalpha():
            continue
        if c not in result:
            result.append(c)
    return result[:10]


def _parse_date(date_header: str) -> tuple[str, float]:
    if not date_header:
        return "", 0.0
    try:
        dt = email_utils.parsedate_to_datetime(date_header)
        if dt is None:
            return date_header, 0.0
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M:%S"), dt.timestamp()
    except Exception:
        return date_header, 0.0


def _connect_imap(email_addr: str, access_token: str) -> imaplib.IMAP4_SSL:
    imap = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT, timeout=30)
    auth = f"user={email_addr}\1auth=Bearer {access_token}\1\1"
    typ, data = imap.authenticate("XOAUTH2", lambda _: auth.encode("utf-8"))
    if typ != "OK":
        detail = data[0].decode("utf-8", "replace") if data and data[0] else "未知错误"
        raise RuntimeError(f"IMAP XOAUTH2 认证失败：{detail}")
    return imap


def fetch_mail_items(
    account: AccountInput,
    *,
    limit: int = 10,
    keyword: str = "",
    mailboxes: tuple[str, ...] = DEFAULT_MAILBOXES,
) -> tuple[list[MailItem], str | None]:
    """Fetch newest mails from configured mailboxes and extract verification codes."""
    limit = max(1, min(int(limit), 100))
    keyword_l = (keyword or "").strip().lower()
    access_token, new_refresh_token = fetch_access_token(account.client_id, account.refresh_token)
    rotated_token = new_refresh_token if new_refresh_token and new_refresh_token != account.refresh_token else None
    imap = _connect_imap(account.email, access_token)
    items: list[MailItem] = []
    try:
        for mailbox in mailboxes:
            typ, _ = imap.select(mailbox, readonly=True)
            if typ != "OK":
                continue
            typ, data = imap.uid("search", None, "ALL")
            if typ != "OK" or not data or not data[0]:
                continue
            uids = data[0].split()
            for uid_b in reversed(uids[-limit:]):
                typ, msg_data = imap.uid("fetch", uid_b, "(RFC822)")
                if typ != "OK" or not msg_data:
                    continue
                raw: bytes | None = None
                for part in msg_data:
                    if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], bytes):
                        raw = part[1]
                        break
                if not raw:
                    continue
                msg = email.message_from_bytes(raw)
                subject = decode_header_value(msg.get("Subject")) or "(No Subject)"
                sender = decode_header_value(msg.get("From")) or "(Unknown Sender)"
                to = decode_header_value(msg.get("To"))
                date_s, ts = _parse_date(msg.get("Date", ""))
                body = extract_body(msg)
                haystack = f"{subject}\n{sender}\n{to}\n{body}"
                if keyword_l and keyword_l not in haystack.lower():
                    continue
                codes = extract_codes(haystack)
                items.append(
                    MailItem(
                        mailbox=mailbox,
                        uid=uid_b.decode("ascii", "replace"),
                        subject=subject,
                        sender=sender,
                        to=to,
                        date=date_s,
                        timestamp=ts,
                        codes=codes,
                        preview=body[:2000],
                    )
                )
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    items.sort(key=lambda x: x.timestamp, reverse=True)
    return items, rotated_token


def mail_to_dict(item: MailItem) -> dict[str, Any]:
    return {
        "mailbox": item.mailbox,
        "uid": item.uid,
        "subject": item.subject,
        "from": item.sender,
        "to": item.to,
        "date": item.date,
        "timestamp": item.timestamp,
        "codes": item.codes,
        "preview": item.preview,
    }
