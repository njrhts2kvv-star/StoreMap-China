const { chromium } = require('playwright');
(async()=>{
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1280,height:720}});
  await page.goto('https://www.toryburch.com/store-locator/',{waitUntil:'domcontentloaded'});
  const inputs = await page.$$eval('input', els => els.map(el => ({placeholder: el.placeholder, name: el.name, type: el.type, id: el.id, className: el.className})));
  console.log(inputs.slice(0,20));
  await browser.close();
})();
