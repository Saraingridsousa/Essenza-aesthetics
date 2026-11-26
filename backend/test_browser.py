"""Browser integration using a temporary database and loopback HTTP server."""
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from playwright.sync_api import sync_playwright, expect
from backend import api

class LocalFlow(unittest.TestCase):
    def test_browser_sqlite_and_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder)/"test.sqlite3"
            api.init(db)
            server = ThreadingHTTPServer(("127.0.0.1",0),api.Handler)
            server.db_path = db
            server.token = "local-test-token-only-not-production"
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            url=f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with self.assertRaises(HTTPError) as e:
                    urlopen(url+"/leads",timeout=5)
                self.assertEqual(e.exception.code,401)
                with self.assertRaises(HTTPError) as e:
                    urlopen(Request(url+"/health",headers={"Origin":"https://untrusted.example"}),timeout=5)
                self.assertEqual(e.exception.code,403)
                with sync_playwright() as p:
                    import os
                    browser=p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"),args=["--no-sandbox"])
                    page=browser.new_page(reduced_motion="reduce")
                    errors=[]
                    page.on("pageerror",lambda err: errors.append(str(err)))
                    page.goto(url)
                    expect(page.locator("#local-connect")).to_be_visible()
                    page.locator("#local-token").fill(server.token)
                    page.locator("#local-login").click()
                    expect(page.locator("#local-status")).to_contain_text("Banco conectado")
                    page.locator("#assistant-text").fill("Como agendar uma avaliação?")
                    page.locator("#assistant-query button").click()
                    expect(page.locator("#assistant-mode")).to_contain_text("base de conhecimento local")
                    page.locator("#sample").click()
                    page.locator("#period").select_option("Tarde")
                    page.locator("#lead-form button[type=submit]").click()
                    expect(page.locator("#form-status")).to_contain_text("registrada no banco local")
                    expect(page.locator("#lead-form button[type=submit]")).to_be_enabled()
                    page.locator("[data-dashboard]").first.click()
                    expect(page.locator("#dashboard")).to_be_visible()
                    expect(page.locator("#queue-counts")).to_contain_text("Pendentes: 1")
                    expect(page.locator("#lead-rows tr")).to_have_count(1)
                    page.locator("#lead-rows select").first.select_option("Agendado")
                    expect(page.locator("#dash-status")).to_contain_text("Status salvo")
                    expect(page.locator("#lead-rows select").first).to_be_enabled()
                    page.locator("#process-event").click()
                    expect(page.locator("#queue-counts")).to_contain_text("Confirmados: 1")
                    page.reload()
                    page.locator("#local-token").fill(server.token)
                    page.locator("#local-login").click()
                    expect(page.locator("#local-status")).to_contain_text("1 lead(s)")
                    page.locator("[data-dashboard]").first.click()
                    expect(page.locator("#lead-rows select").first).to_have_value("Agendado")
                    expect(page.locator("#queue-counts")).to_contain_text("Confirmados: 1")
                    expect(page.locator("#status-history")).to_contain_text("Novo → Agendado")
                    self.assertFalse(errors,errors)
                    browser.close()
                self.assertEqual(api.metrics(db)["total"],1)
                self.assertEqual(api.metrics(db)["outbox"],{"sent":1})
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

if __name__=="__main__":
    unittest.main()
