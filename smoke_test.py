import os
from pathlib import Path
from playwright.sync_api import sync_playwright

p = Path(__file__).resolve().parent / 'index.html'
def open_demo(page):
    from base64 import b64encode
    svg = p.parent / 'assets' / 'essenza-mark.svg'
    uri = 'data:image/svg+xml;base64,' + b64encode(svg.read_bytes()).decode('ascii')
    page.set_content(p.read_text(encoding='utf-8').replace('assets/essenza-mark.svg', uri))
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH'), args=['--no-sandbox'])
    page = b.new_page(viewport={'width':1440,'height':1000}, accept_downloads=True)
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    open_demo(page)
    page.screenshot(path=str(p.parent/'preview.png'))
    assert page.locator('h1').is_visible()
    assert page.locator('.header .brand img').evaluate('(i)=>i.complete && i.naturalWidth>0')
    assert page.locator('.gallery-card').count() == 3
    assert page.locator('img[data-photo][src]').count() == 0
    page.locator('[data-assistant=price]').click()
    assert 'não possui preços' in page.locator('#assistant-answer').inner_text()
    page.locator('[data-category=Corporal]').click()
    assert page.locator('.service:visible').count() == 2
    page.locator('[data-category=Todos]').click()
    assert page.locator('.service:visible').count() == 6
    page.locator('[data-service]').nth(1).click()
    assert page.locator('#service').input_value() == 'Massagem facial'
    page.locator('#sample').click()
    page.locator('#period').select_option('Tarde')
    page.locator('button[type=submit]').click()
    assert 'registrada' in page.locator('#form-status').inner_text()
    page.locator('[data-dashboard]').first.click()
    assert page.locator('#lead-rows tr').count() == 4
    assert page.locator('#kpis strong').first.inner_text() == '4'
    assert page.locator('#lead-rows tr').first.locator('td').last.inner_text() == 'Tarde'
    assert page.locator('#funnel .barrow').count() == 4
    page.locator('#lead-search').fill('Visitante')
    assert page.locator('#lead-rows tr').count() == 1
    page.locator('#lead-search').fill('')
    page.locator('#lead-rows select').first.select_option('Convertido')
    assert page.locator('#commercial-metrics strong').first.inner_text() == '25%'
    page.locator('#status-filter').select_option('Convertido')
    assert page.locator('#lead-rows tr').count() == 1
    page.locator('#status-filter').select_option('Todos')
    page.locator('#lead-rows select').first.select_option('Agendado')
    page.locator('#status-filter').select_option('Agendado')
    assert page.locator('#lead-rows tr').count() == 2
    page.locator('#status-filter').select_option('Todos')
    page.screenshot(path=str(p.parent/'painel.png'), full_page=True)
    with page.expect_download() as d:
        page.locator('#export').click()
    assert d.value.suggested_filename == 'essenza-leads-demo.csv'
    csv = Path(d.value.path()).read_text(encoding='utf-8-sig')
    assert all(x in csv for x in ('visitante@example.com','Período','Tarde'))
    page.locator('#close-dashboard').click()
    page.locator('[data-service]').nth(1).click()
    page.locator('#sample').click()
    page.locator('button[type=submit]').click()
    assert 'não foi duplicado' in page.locator('#form-status').inner_text()
    page.locator('#email').fill('not-demo@gmail.com')
    assert not page.locator('#email').evaluate('(e)=>e.checkValidity()')
    page.locator('[data-dashboard]').first.click()
    page.on('dialog', lambda d: d.accept())
    page.locator('#reset').click()
    assert page.locator('#lead-rows tr').count() == 3
    page.locator('#close-dashboard').click()
    for w in [320,390,768,801,1024,1440]:
        page = b.new_page(viewport={'width':w,'height':850})
        page.on('pageerror', lambda e: errs.append(str(e)))
        open_demo(page)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), w
        if w == 390:
            assert page.locator('.floating-book').is_visible()
            page.locator('.menu-toggle').click()
            assert page.locator('#nav').is_visible()
            page.keyboard.press('Escape')
            assert not page.locator('#nav').is_visible()
            page.screenshot(path=str(p.parent/'mobile.png'))
        page.locator('[data-dashboard]').first.click()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), ('dashboard',w)
        page.close()
    reduced = b.new_page(viewport={'width':390,'height':850}, reduced_motion='reduce')
    open_demo(reduced)
    assert not reduced.locator('html').evaluate("(el)=>el.classList.contains('motion-ready')")
    assert reduced.locator('h1').evaluate("(el)=>getComputedStyle(el).animationName === 'none'")
    reduced.close()
    assert not errs, errs
    b.close()
print('PASS: logo, service filters, lead capture, validation, duplicate prevention, contact period, search, funnel, CSV, reset, mobile navigation and six viewport widths.')
