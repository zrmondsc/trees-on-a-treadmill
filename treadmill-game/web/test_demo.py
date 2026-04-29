"""Test the auto-play demo mode."""
import asyncio
import threading
import http.server
import socketserver
import os

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8765

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WEB_DIR, **kw)
    def log_message(self, *a, **kw): pass

def start_server():
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd

async def main():
    from playwright.async_api import async_playwright
    httpd = start_server()
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            ctx = await browser.new_context(viewport={"width": 1400, "height": 1100})
            page = await ctx.new_page()
            errors = []
            page.on("pageerror", lambda exc: errors.append(f"PAGEERROR: {exc}"))
            page.on("console", lambda msg: errors.append(f"console.{msg.type}: {msg.text}") if msg.type in ("error",) else None)

            await page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")

            # Click the demo (auto-play) button without picking an archetype
            await page.click('#demo-btn')
            await page.wait_for_timeout(800)
            await page.screenshot(path="/tmp/demo-early.png", full_page=True)

            # Let the demo run further
            await page.wait_for_timeout(6000)
            await page.screenshot(path="/tmp/demo-mid.png", full_page=True)

            # Wait for end screen to appear (TOTAL_YEARS=25 * 600ms = ~15s total)
            await page.wait_for_selector("#end-screen:not(.hidden)", timeout=20000)
            await page.screenshot(path="/tmp/demo-end.png", full_page=True)

            # Click "Begin another season" to make sure restart from end works
            await page.click('#restart-btn')
            await page.wait_for_timeout(300)
            # Now confirm setup screen is back
            assert await page.is_visible('#setup-screen')
            await page.screenshot(path="/tmp/demo-back-to-setup.png", full_page=True)

            # Pick an archetype and start a real game (decision panel must render)
            await page.click('button.archetype[data-key="intensive"]')
            await page.wait_for_timeout(150)
            await page.click('#start-btn')
            await page.wait_for_timeout(300)
            assert await page.is_visible('#plant-acres'), "Decision panel inputs missing after demo→real-game transition"
            await page.screenshot(path="/tmp/demo-restart-real-game.png", full_page=True)

            print("ERRORS:" if errors else "no errors")
            for e in errors: print(" ", e)
            await browser.close()
    finally:
        httpd.shutdown()

asyncio.run(main())
