import os
import httpx
import logging
from dotenv import load_dotenv

logger = logging.getLogger("telegram_service")

class TelegramService:
    @staticmethod
    def send_message(text: str) -> bool:
        """
        Sends a message to the configured Telegram chat ID using the bot token.
        """
        load_dotenv()
        token = os.getenv("TELEGRAM_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        if not token or not chat_id:
            # Silently skip if Telegram is not configured
            return False

        # Clean/sanitize target inputs
        if "your_" in token or "your_" in chat_id:
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        try:
            # Synchronous request helper to avoid async loops in standard logging callbacks
            response = httpx.post(url, json=payload, timeout=10.0)
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully.")
                return True
            else:
                logger.error(f"Telegram API returned status code {response.status_code}: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending message to Telegram: {e}")
            return False
