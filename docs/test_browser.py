"""Run a local HTTP server and Playwright test in the same Python process."""
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
    def log_message(self, *a, **kw):
        pass

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
            await page.screenshot(path="/tmp/01-setup.png", full_page=True)

            await page.click('button.archetype[data-key="intensive"]')
            await page.wait_for_timeout(150)
            await page.click('#start-btn')
            await page.wait_for_timeout(400)
            await page.screenshot(path="/tmp/02-year0.png", full_page=True)

            for _ in range(8):
                await page.click('#advance-btn')
                await page.wait_for_timeout(80)
            await page.screenshot(path="/tmp/03-year8.png", full_page=True)

            await page.fill('#plant-acres', '200')
            await page.click('#advance-btn')
            await page.wait_for_timeout(80)

            for _ in range(15):
                await page.click('#advance-btn')
                await page.wait_for_timeout(60)
            await page.screenshot(path="/tmp/04-late.png", full_page=True)

            # Run remaining years until end screen appears
            while not (await page.is_visible('#end-screen')):
                if await page.is_visible('#advance-btn') and not (await page.get_attribute('#advance-btn', 'disabled')):
                    await page.click('#advance-btn')
                    await page.wait_for_timeout(60)
                else:
                    break
            await page.screenshot(path="/tmp/05-end.png", full_page=True)

            print("ERRORS:" if errors else "no errors")
            for e in errors:
                print("  ", e)
            await browser.close()
    finally:
        httpd.shutdown()

asyncio.run(main())
