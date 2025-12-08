const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const context = await browser.newContext({
    locale: 'zh-CN',
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  });
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });
  const page = await context.newPage();
  page.on('response', async (resp) => {
    const url = resp.url();
    const ctype = resp.headers()['content-type'] || '';
    if (ctype.includes('application/json') && /store/i.test(url)) {
      try {
        const text = await resp.text();
        console.log('JSON resp', resp.status(), url, text.slice(0, 200));
      } catch (e) {}
    }
  });
  try {
    const resp = await page.goto('https://www.dior.cn/fashion/stores/zh_cn/search', { waitUntil: 'domcontentloaded', timeout: 45000 });
    console.log('goto status', resp ? resp.status() : 'no resp');
    console.log('title', await page.title());
    await page.waitForTimeout(15000);
    await page.screenshot({ path: 'dior_store_page.png', fullPage: true }).catch(() => {});
  } catch (err) {
    console.error('error goto', err);
  } finally {
    await browser.close();
  }
})();
