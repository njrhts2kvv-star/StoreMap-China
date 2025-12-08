const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const browser = await chromium.launch({ headless: false, args: ['--disable-blink-features=AutomationControlled'] });
  const context = await browser.newContext({
    locale: 'zh-CN',
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    geolocation: { latitude: 39.9042, longitude: 116.4074 },
    permissions: ['geolocation'],
  });
  await context.addInitScript(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  });
  const page = await context.newPage();
  let saved = false;
  page.on('response', async (resp) => {
    const url = resp.url();
    const ctype = resp.headers()['content-type'] || '';
    if (!saved && ctype.includes('application/json') && url.includes('/search?')) {
      try {
        const text = await resp.text();
        fs.writeFileSync('dior_search_response.json', text, 'utf-8');
        const data = JSON.parse(text);
        console.log('saved search json. keys:', Object.keys(data));
        console.log('counts', data?.storeList?.length || 0);
        saved = true;
      } catch (e) {
        console.error('parse error', e);
      }
    }
  });
  try {
    await page.goto('https://www.dior.cn/fashion/stores/zh_cn/search', { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(20000);
  } catch (err) {
    console.error('error goto', err);
  } finally {
    await browser.close();
  }
})();
