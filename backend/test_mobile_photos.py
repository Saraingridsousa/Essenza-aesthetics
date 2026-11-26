"""Check native mobile photo loading and layout stability on a delayed network."""
import os
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect
from backend import api

class MobilePhotoTests(unittest.TestCase):
    def test_delayed_photos_keep_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/"test.sqlite3"
            api.init(db)
            server=ThreadingHTTPServer(("127.0.0.1",0),api.Handler)
            server.db_path=db
            server.token="test-local-token-only-0123456789"
            thread=threading.Thread(target=server.serve_forever,daemon=True)
            thread.start()
            try:
                with sync_playwright() as p:
                    b=p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"),args=["--no-sandbox"])
                    page=b.new_page(viewport={"width":390,"height":844},is_mobile=True,has_touch=True,device_scale_factor=2)
                    errors=[]
                    page.on("pageerror",lambda e:errors.append(str(e)))
                    pending=[]
                    page.route("**/assets/photos/*.webp",lambda route:pending.append(route))
                    page.goto(f"http://127.0.0.1:{server.server_address[1]}/",wait_until="domcontentloaded")
                    expect(page.locator("#hero-photo")).to_have_attribute("loading","eager")
                    expect(page.locator("#sobre img[data-local-photo]")).to_have_attribute("loading","eager")
                    expect(page.locator("#procedimentos img[data-local-photo]").first).to_have_attribute("loading","lazy")
                    def positions():
                        return page.evaluate("""()=>({height:document.documentElement.scrollHeight,
                          sections:[...document.querySelectorAll('main section')].map(x=>[x.id,Math.round(x.getBoundingClientRect().top+scrollY),Math.round(x.getBoundingClientRect().height)])})""")
                    before=positions()
                    page.locator("#sobre").scroll_into_view_if_needed()
                    page.wait_for_timeout(200)
                    scroll=page.evaluate("scrollY")
                    # Fulfill the delayed requests with a real, neutral stock photo from the repository.
                    payload=(Path(__file__).resolve().parents[1]/"assets/photos/room.webp").read_bytes()
                    for route in pending[:]:
                        route.fulfill(status=200,content_type="image/webp",body=payload)
                    expect(page.locator("#sobre img[data-local-photo]")).to_have_class("local-editorial photo-ready")
                    self.assertEqual(before,positions())
                    self.assertLessEqual(abs(page.evaluate("scrollY")-scroll),1)
                    self.assertFalse(errors,errors)
                    b.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
