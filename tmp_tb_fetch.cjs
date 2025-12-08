const { chromium } = require('playwright');
(async()=>{
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1280,height:720}});
  page.on('request',req=>{const url=req.url(); if(url.includes('store')||url.includes('locator')||url.includes('api/prod-r2')) console.log('REQ',req.method(),url);});
  page.on('response',res=>{const url=res.url(); if(url.includes('store')||url.includes('locator')||url.includes('api/prod-r2')) console.log('RES',res.status(),url);});
  await page.goto('https://www.toryburch.com/store-locator/',{waitUntil:'domcontentloaded'});
  const input = await page.waitForSelector('input[placeholder="Suchen"]',{timeout:15000});
  await input.fill('China',{force:true}).catch(()=>{});
  await page.keyboard.press('Enter').catch(()=>{});
  await page.waitForTimeout(10000);
  await browser.close();
})();
