const { chromium } = require('playwright');
(async()=>{
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1280,height:720}});
  await page.goto('https://www.toryburch.com/zh/store-locator/cn/',{waitUntil:'domcontentloaded'});
  await page.waitForTimeout(10000);
  const items = await page.$$eval('[class*="stores-item__title"]',els=>els.map(el=>el.textContent.trim()));
  console.log('items len',items.length);
  console.log(items.slice(0,20));
  await browser.close();
})();
