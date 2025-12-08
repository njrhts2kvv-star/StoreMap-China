const { chromium } = require('playwright');
(async()=>{
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1280,height:720}});
  page.on('request',req=>{const url=req.url(); if(url.includes('store')||url.includes('locator')||url.includes('api/prod-r2')) console.log('REQ',req.method(),url);});
  page.on('response',res=>{const url=res.url(); if(url.includes('store')||url.includes('locator')||url.includes('api/prod-r2')) console.log('RES',res.status(),url);});
  await page.goto('https://www.toryburch.com/de-de/store-locator/all-stores/',{waitUntil:'networkidle', timeout:60000});
  await page.waitForTimeout(5000);
  await browser.close();
})();
