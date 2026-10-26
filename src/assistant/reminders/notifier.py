"""Bộ phát thông báo Windows Toast và tích hợp Telegram (Reminder Notifier).

Tuân thủ:
- Phát Windows Toast với âm thanh nhắc việc rõ ràng, không đòi hỏi quyền Admin.
- Tự động fallback an toàn (in console, âm thanh hệ thống) nếu môi trường không hỗ trợ toast.
- Gửi thông báo Telegram song song (nếu cấu hình bot token trong keyring và chat_id).
- Mất kết nối mạng KHÔNG làm gián đoạn thông báo Toast trên máy (Nguyên tắc 2 & 9).
"""

import asyncio
import logging
import os
import sys

logger = logging.getLogger("assistant.reminders.notifier")

# Kiểm tra thư viện winotify
try:
    from winotify import Notification, audio
    HAS_WINOTIFY = True
except ImportError:
    HAS_WINOTIFY = False


def _get_telegram_bot_token() -> str | None:
    """Đọc TELEGRAM_BOT_TOKEN từ Windows Credential Manager hoặc biến môi trường."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token and token.strip():
        return token.strip()

    try:
        import keyring

        token_kr = keyring.get_password("TroLyAI", "TELEGRAM_BOT_TOKEN")
        if token_kr and token_kr.strip():
            return token_kr.strip()
    except Exception:
        pass

    return None


async def send_telegram_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Gửi tin nhắn qua Telegram Bot API (không làm crash hệ thống nếu mất mạng)."""
    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"⏰ [TRỢ LÝ AI — NHẮC VIỆC]\n{text}",
        "parse_mode": "HTML",
    }

    try:
        import httpx

        async with httpx.AsyncClient(timeout=3.5) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as err:
        logger.warning("Không thể gửi thông báo Telegram (có thể do mất mạng): %s", err)
        return False


def show_windows_toast(
    message: str,
    title: str = "⏰ Lời Nhắc Việc — Trợ Lý AI",
    app_id: str = "TroLy.AI.Assistant",
) -> bool:
    """Hiển thị thông báo Windows Toast trên màn hình kèm âm thanh."""
    if HAS_WINOTIFY and sys.platform == "win32":
        try:
            toast = Notification(
                app_id=app_id,
                title=title,
                msg=message,
                duration="short",
            )
            toast.set_audio(audio.Reminder, loop=False)
            toast.show()
            return True
        except Exception as err:
            logger.warning("Lỗi phát Windows Toast qua winotify: %s", err)

    # Dự phòng 1: Phát âm thanh hệ thống Windows nếu có
    if sys.platform == "win32":
        try:
            import winsound

            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception:
            pass

    # Dự phòng 2: In trực tiếp ra console
    print(f"\n🔔 [{title.upper()}]: {message}\n")
    return True


async def notify_reminder(
    message: str,
    title: str = "⏰ Lời Nhắc Việc — Trợ Lý AI",
    telegram_chat_id: str | None = None,
) -> dict[str, bool]:
    """Phát thông báo hoàn chỉnh (Windows Toast + Telegram đồng thời)."""
    # 1. Phát Toast trên Windows ngay lập tức (không phụ thuộc mạng)
    toast_ok = show_windows_toast(message=message, title=title)

    # 2. Gửi Telegram (nếu có cấu hình)
    tg_ok = False
    bot_token = _get_telegram_bot_token()
    if bot_token and telegram_chat_id:
        try:
            tg_ok = await send_telegram_message(
                bot_token=bot_token,
                chat_id=telegram_chat_id,
                text=message,
            )
        except Exception:
            tg_ok = False

    return {"toast": toast_ok, "telegram": tg_ok}


def notify_sync(
    message: str,
    title: str = "⏰ Lời Nhắc Việc — Trợ Lý AI",
    telegram_chat_id: str | None = None,
) -> None:
    """Hàm wrapper đồng bộ để gọi thông báo nhanh chóng."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(notify_reminder(message, title, telegram_chat_id))
    except RuntimeError:
        asyncio.run(notify_reminder(message, title, telegram_chat_id))
