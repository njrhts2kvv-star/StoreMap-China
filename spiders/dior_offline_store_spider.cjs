const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const OUTPUT = path.join(__dirname, '..', '各品牌爬虫数据', 'Dior_offline_stores.csv');
const HEADER = ['uuid','brand','name','lat','lng','address','province','city','phone','business_hours','opened_at','status','raw_source'];
const COORDS = [
  [39.9042,116.4074],[31.2304,121.4737],[23.1291,113.2644],[22.5431,114.0579],[30.5728,104.0668],[29.5630,106.5516],[34.3416,108.9398],[41.8057,123.4315],[38.9140,121.6147],[45.8038,126.5349],[25.0453,102.7103],[26.0745,119.2965],[24.4798,118.0894],[30.2741,120.1551],[32.0603,118.7969],[36.0671,120.3826],[37.8706,112.5489],[36.0610,103.8343],[20.0440,110.1999],[22.8170,108.3669],[43.8256,87.6168],[29.6520,91.1720],[31.2989,120.5853],[30.5928,114.3055],[34.7473,113.6249],[31.8206,117.2273],[28.2282,112.9388],[38.4872,106.2309],[25.2744,110.2900],[39.1256,117.1902]
];

function uuidv4(){return'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,c=>{const r=Math.random()*16|0,v=c==='x'?r:(r&0x3)|0x8;return v.toString(16);});}
function toCsvValue(val){if(val===null||val===undefined)return'';const str=String(val).replace(/\r?\n/g,' ');if(str.includes(',')||str.includes('"'))return '"'+str.replace(/"/g,'""')+'"';return str;}
function writeCsv(rows){const dir=path.dirname(OUTPUT);if(!fs.existsSync(dir))fs.mkdirSync(dir,{recursive:true});const lines=[HEADER.join(',')];for(const row of rows){lines.push(HEADER.map(k=>toCsvValue(row[k])).join(','));}fs.writeFileSync(OUTPUT,'\ufeff'+lines.join('\n'),'utf-8');console.log(`[保存] 写入 ${OUTPUT} 共 ${rows.length} 条`);} 

async function fetchEntities(page, lat, lng){
  const result = await page.evaluate(async ({lat,lng})=>{
    const url=`https://www.dior.cn/fashion/stores/zh_cn/search?q=${lat},${lng}&l=zh_Hans`;
    const resp=await fetch(url,{headers:{'Accept':'application/json, text/plain, */*'}});
    const text=await resp.text();
    let json=null;try{json=JSON.parse(text);}catch(e){return{status:resp.status,count:0,entities:[],textHead:text.slice(0,100)};}
    return{status:resp.status,count:(json?.response?.count)||0,entities:json?.response?.entities||[]};
  },{lat,lng});
  console.log('fetch', lat, lng, 'status', result.status, 'count', result.count);
  if(result.status!==200)return[];
  return result.entities;
}

function mapStore(entity){
  const profile=entity.profile||{};const address=profile.address||{};const coords=entity.yextDisplayCoordinate||entity.yextRoutableCoordinate||{};const lat=coords.lat||coords.latitude;const lng=coords.long||coords.longitude;const hours=profile.hours;let businessHours='';if(hours&&Array.isArray(hours.normalHours)){businessHours=JSON.stringify(hours.normalHours);}const line1=address.line1||'';const line2=address.line2||'';const fullAddress=[line1,line2,address.city,address.region].filter(Boolean).join(' ');const phone=(profile.mainPhone&&(profile.mainPhone.display||profile.mainPhone.number))||'';return{uuid:uuidv4(),brand:'Dior',name:entity.name||profile.locationName||'',lat:lat?Number(lat).toFixed(6):'',lng:lng?Number(lng).toFixed(6):'',address:fullAddress,province:address.region||'',city:address.city||'',phone,business_hours:businessHours,opened_at:new Date().toISOString().slice(0,10),status:'营业中',raw_source:JSON.stringify(entity)};}

(async()=>{
  const browser=await chromium.launch({headless:false,args:['--disable-blink-features=AutomationControlled']});
  const context=await browser.newContext({locale:'zh-CN',userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'});
  await context.addInitScript(()=>{Object.defineProperty(navigator,'webdriver',{get:()=>undefined});});
  const page=await context.newPage();
  await page.goto('https://www.dior.cn/fashion/stores/zh_cn/search',{waitUntil:'domcontentloaded',timeout:45000});
  await page.waitForTimeout(5000);

  const seen=new Map();
  for(const [lat,lng] of COORDS){
    const entities=await fetchEntities(page,lat,lng);
    for(const ent of entities){
      const id = ent?.distance?.id || ent?.url || JSON.stringify(ent.profile?.address||{});
      if(!id || seen.has(id)) continue;
      seen.set(id,mapStore(ent));
    }
    await page.waitForTimeout(800);
  }

  await browser.close();
  writeCsv(Array.from(seen.values()));
})();
