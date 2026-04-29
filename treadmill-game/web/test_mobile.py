"""Verify rainfed archetype renders correctly."""
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

            # Mobile
            ctx = await browser.new_context(viewport={"width": 390, "height": 844})
            page = await ctx.new_page()
            errors = []
            page.on("pageerror", lambda exc: errors.append(f"PAGEERROR: {exc}"))
            await page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle")
            await page.screenshot(path="/tmp/mobile-setup.png", full_page=True)
            await page.click('button.archetype[data-key="rainfed"]')
            await page.wait_for_timeout(150)
            await page.click('#start-btn')
            await page.wait_for_timeout(300)
            await page.screenshot(path="/tmp/mobile-year0-rainfed.png", full_page=True)
            for _ in range(10):
                await page.click('#advance-btn')
                await page.wait_for_timeout(80)
            await page.screenshot(path="/tmp/mobile-year10-rainfed.png", full_page=True)

            print("ERRORS:" if errors else "no errors")
            for e in errors: print(" ", e)

            await browser.close()
    finally:
        httpd.shutdown()

asyncio.run(main())
