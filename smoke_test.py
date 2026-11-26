import os
from playwright.sync_api import sync_playwright
from pathlib import Path

p = Path(__file__).resolve().parent / 'index.html'
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH'), args=['--no-sandbox'])
    page = b.new_page(viewport={'width':1440,'height':1000}, accept_downloads=True)
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.set_content(p.read_text(encoding='utf-8'))
    page.screenshot(path=str(p.parent/'preview.png'), full_page=False)
    assert page.locator('h1').is_visible()
    page.locator('[data-service]').nth(1).click()
    assert page.locator('#service').input_value() == 'Massagem facial'
    page.locator('#sample').click()
    page.locator('button[type=submit]').click()
    assert 'registrada' in page.locator('#form-status').inner_text()
    page.locator('[data-dashboard]').first.click()
    assert page.locator('#lead-rows tr').count() == 4
    assert page.locator('#kpis strong').first.inner_text() == '4'
    page.locator('#lead-rows select').first.select_option('Agendado')
    page.locator('#status-filter').select_option('Agendado')
    assert page.locator('#lead-rows tr').count() == 2
    page.locator('#status-filter').select_option('Todos')
    page.screenshot(path=str(p.parent/'painel.png'), full_page=True)
    with page.expect_download() as d:
        page.locator('#export').click()
    assert d.value.suggested_filename == 'essenza-leads-demo.csv'
    assert 'visitante@example.com' in Path(d.value.path()).read_text(encoding='utf-8-sig')
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
    for w in [320,390,768,1024,1440]:
        page = b.new_page(viewport={'width':w,'height':850})
        page.on('pageerror', lambda e: errs.append(str(e)))
        page.set_content(p.read_text(encoding='utf-8'))
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), w
        if w == 390:
            page.locator('.menu-toggle').click()
            assert page.locator('#nav').is_visible()
            page.keyboard.press('Escape')
            assert not page.locator('#nav').is_visible()
            page.screenshot(path=str(p.parent/'mobile.png'), full_page=False)
    assert not errs, errs
    b.close()
print('PASS: lead capture, duplicate prevention, validation, statuses, filtering, CSV, reset, navigation and five viewport widths.')
