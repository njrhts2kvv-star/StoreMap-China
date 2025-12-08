const { chromium } = require('playwright');
const fs = require('fs');
(async()=>{
  const browser = await chromium.launch({headless:true});
  const page = await browser.newPage({viewport:{width:1280,height:720}});
  const captured = [];
  page.on('response', async (res)=>{
    const url = res.url();
    if(/Stores-|store-locator|storelocator|FindByGeo/i.test(url)){
      try{
        const ct = res.headers()['content-type']||'';
        if(ct.includes('json') || url.includes('Find') || url.includes('stores')){
          const text = await res.text();
          captured.push({url, status: res.status(), ct, text});
        }
      }catch(e){}
    }
  });
  await page.goto('https://www.mcmworldwide.com/en-us/store-locator/all-stores/', {waitUntil:'networkidle', timeout:90000});
  await page.waitForTimeout(5000);
  const html = await page.content();
  fs.writeFileSync('tmp_mcm_page.html', html);
  fs.writeFileSync('tmp_mcm_responses.json', JSON.stringify(captured,null,2));
  await browser.close();
})();
