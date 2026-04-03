import asyncio
from playwright.async_api import async_playwright

async def login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://visa.vfsglobal.com/ind/en/deu/login")

        print("\n👉 Complete login:")
        print("1. Pass Cloudflare")
        print("2. Enter OTP")
        print("3. Wait on dashboard\n")

        # Wait for you
        await page.wait_for_timeout(120000)

        await context.storage_state(path="state.json")

        print("✅ Session saved successfully!")

        await browser.close()

asyncio.run(login())
##
