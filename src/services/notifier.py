import requests

from src.config.settings import (
    load_env,
    get_telegram_bot_token,
    get_telegram_chat_id,
)


class TelegramNotifier:
    def __init__(self):
        load_env()
        self._bot_token = get_telegram_bot_token()
        self._chat_id = get_telegram_chat_id()
        if not self._bot_token or not self._chat_id:
            print("Warning: Telegram credentials not set.")
            self.enabled = False
        else:
            self.enabled = True
            self.base_url = f"https://api.telegram.org/bot{self._bot_token}/sendMessage"

    def send_message(self, message: str):
        if not self.enabled:
            print("Telegram notification disabled (missing credentials).")
            return

        try:
            payload = {
                "chat_id": self._chat_id,
                "text": message,
                "parse_mode": "Markdown" # Or HTML
            }
            response = requests.post(self.base_url, data=payload, timeout=20, verify=False) # Debug: verify=False
            response.raise_for_status()
            print("Telegram message sent successfully.")
        except Exception as e:
            print(f"Error sending Telegram message details: {type(e).__name__}: {e}")

    def format_and_send(self, agency_name: str, title: str, link: str, analysis: dict):
        if not analysis:
            return

        risk_emoji = "🔴" if analysis.get('risk_level') == 'High' else "🟡" if analysis.get('risk_level') == 'Medium' else "🟢"

        summary_text = ""
        for item in analysis.get('summary', []):
            summary_text += f"- {item}\n"

        msg = (
            f"*{agency_name}* | {risk_emoji} {analysis.get('risk_level', 'Unknown')}\n\n"
            f"**{title}**\n\n"
            f"📝 *Summary*\n{summary_text}\n"
            f"💥 *Banking Impact*\n{analysis.get('impact_analysis', 'N/A')}\n\n"
            f"[Link]({link})"
        )

        self.send_message(msg)

if __name__ == "__main__":
    notifier = TelegramNotifier()
    try:
        notifier.send_message("MarketPulse-Reg Pilot: Test Message 🚀")
    except Exception:
        import traceback
        traceback.print_exc()
