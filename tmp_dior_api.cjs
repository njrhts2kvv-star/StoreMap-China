const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const context = await browser.newContext({
    locale: 'zh-CN',
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
  });
  await context.addInitScript(() => { Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); });
  const page = await context.newPage();
  await page.goto('https://www.dior.cn/fashion/stores/zh_cn/search', { waitUntil: 'domcontentloaded', timeout: 45000 });
  const data = await page.evaluate(async () => {
    const resp = await fetch('https://www.dior.cn/fashion/stores/zh_cn/search?q=39.9042,116.4074&l=zh_Hans', {
      headers: { 'Accept': 'application/json, text/plain, */*' }
    });
    return { status: resp.status, text: await resp.text() };
  });
  console.log('status', data.status);
  console.log('text head', data.text.slice(0,200));
  await browser.close();
})();
