import os
import json
import asyncio
import random
from datetime import datetime

import requests
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

# -------------------------------
# CONFIG
# -------------------------------
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

DASHBOARD_URL = "https://visa.vfsglobal.com/ind/en/deu/dashboard"
STATE_FILE = "last_state.json"

CENTRES = {
    "Bangalore": "Bangalore - Germany Visa Application Centre",
    "Mumbai": "Mumbai - Germany Visa Application Centre",
    "Cochin": "Cochin - Visa Application Centre"
}

# -------------------------------
# TELEGRAM
# -------------------------------
def send_telegram(msg, urgent=False):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "👉 Open VFS Portal",
                        "url": DASHBOARD_URL
                    }
                ]
            ]
        }
    }

    requests.post(url, json=payload)

    # 🚨 Extra urgent alert
    if urgent:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": "🚨 URGENT: Slots AVAILABLE! Book immediately!"
        })


def send_login_alert():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    msg = """⚠️ <b>VFS Session Expired</b>

🔐 Login required to continue tracking visa slots

👉 Steps:
1. Run login.py
2. Complete OTP
3. Bot will resume automatically

⏳ Takes less than 1 minute
"""

    payload = {
        "chat_id": CHAT_ID,
        "text": msg,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {
                        "text": "👉 Open VFS Login",
                        "url": "https://visa.vfsglobal.com/ind/en/deu/login"
                    }
                ]
            ]
        }
    }

    requests.post(url, json=payload)


# -------------------------------
# STATE HANDLING
# -------------------------------
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# -------------------------------
# HELPERS
# -------------------------------
def format_status(status):
    if status == "AVAILABLE":
        return "🚀 <b>Slots Available</b>"
    elif status == "WAITLIST":
        return "⏳ Waitlist Open"
    return "❌ No Slots"


def detect_status(content):
    c = content.lower()

    if "no appointment slots" in c:
        return "NO_SLOTS"
    elif "waitlist" in c:
        return "WAITLIST"
    else:
        return "AVAILABLE"


async def select_appointment(page, location):
    centre_name = CENTRES[location]

    await page.wait_for_selector("text=Appointment Details", timeout=15000)

    # Application Centre
    await page.click("text=Choose your Application Centre")
    await page.wait_for_timeout(random.randint(1500, 3000))

    locator = page.locator(f"text={centre_name}").first
    await locator.scroll_into_view_if_needed()
    await locator.click()

    # Category
    await page.click("text=Choose your appointment category")
    await page.wait_for_timeout(2000)
    await page.click("text=Employment")

    # Sub-category
    await page.click("text=Choose your sub-category")
    await page.wait_for_timeout(2000)
    await page.click("text=Opportunity Card")

    await page.wait_for_timeout(5000)


# -------------------------------
# MAIN BOT LOGIC
# -------------------------------
async def run_bot():
    previous_state = load_state()
    current_state = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(storage_state="state.json")
        page = await context.new_page()

        for loc in CENTRES.keys():

            print(f"Checking {loc}...")

            await page.goto(DASHBOARD_URL)
            await page.wait_for_timeout(4000)

            # 🔐 Session expired check
            if "login" in page.url or "sign in" in (await page.content()).lower():
                send_login_alert()
                return

            # Start booking
            await page.get_by_role("button", name="Start New Booking").click()
            await page.wait_for_timeout(5000)

            # Select flow
            await select_appointment(page, loc)

            content = await page.content()
            status = detect_status(content)

            current_state[loc] = status

            await page.wait_for_timeout(random.randint(2000, 4000))

        await browser.close()

    # -------------------------------
    # Compare & Notify
    # -------------------------------
    changed = False

    for loc, status in current_state.items():
        if previous_state.get(loc) != status:
            changed = True
            break

    if not changed:
        return

    msg = f"""🇩🇪 <b>Germany Opportunity Card Visa Slots</b>

📍 Bangalore → {format_status(current_state.get("Bangalore"))}
📍 Cochin → {format_status(current_state.get("Cochin"))}
📍 Mumbai → {format_status(current_state.get("Mumbai"))}

⚡ <b>Act fast — slots fill quickly!</b>

⏰ {datetime.now().strftime('%H:%M %d-%b')}
"""

    urgent_flag = any(v == "AVAILABLE" for v in current_state.values())

    send_telegram(msg, urgent=urgent_flag)

    save_state(current_state)


# -------------------------------
# CLOUD RUN ENTRY (HTTP)
# -------------------------------
from flask import Flask
import os

app = Flask(__name__)

@app.route("/")
def run():
    asyncio.run(run_bot())
    return "Bot executed!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
