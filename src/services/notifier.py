import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

class TelegramNotifier:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            print("Warning: Telegram credentials not set.")
            self.enabled = False
        else:
            self.enabled = True
            self.base_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    def send_message(self, message: str):
        if not self.enabled:
            print("Telegram notification disabled (missing credentials).")
            return

        try:
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
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
