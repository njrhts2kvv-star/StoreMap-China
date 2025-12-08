const { chromium } = require("playwright");

const PAGE_URL =
  process.env.TESLA_PAGE_URL ||
  "https://www.tesla.cn/findus?bounds=40.11393476927143%2C116.77453305675563%2C39.715481225762645%2C116.03346694324422";
const LIST_URL =
  process.env.TESLA_LIST_URL ||
  "https://www.tesla.cn/api/findus/get-locations?country=CN&view=list&functionType=tesla_center_sales";

async function fetchLocations() {
  const browser = await chromium.launch({
    headless: false,
    args: ["--disable-blink-features=AutomationControlled"],
  });

  try {
    const context = await browser.newContext({
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
      locale: "zh-CN",
      viewport: { width: 1280, height: 720 },
    });
    const page = await context.newPage();

    await page.goto(PAGE_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
    // 等待挑战完成并产生任意数据请求
    await page
      .waitForResponse(
        (resp) =>
          resp.url().includes("get-locations") ||
          resp.url().includes("findus/_next") ||
          resp.url().includes("findus?bounds"),
        { timeout: 45_000 }
      )
      .catch(() => {});
    await page.waitForTimeout(5_000);

    const resp = await page.request.get(LIST_URL, { timeout: 60_000 });
    if (!resp.ok()) {
      throw new Error(`list request failed: ${resp.status()} ${resp.statusText()}`);
    }
    const json = await resp.json();
    const data = json?.data?.data;
    if (!Array.isArray(data)) {
      throw new Error("unexpected payload structure");
    }
    process.stdout.write(JSON.stringify(data));
  } finally {
    await browser.close();
  }
}

fetchLocations().catch((err) => {
  console.error(err?.stack || err?.message || err);
  process.exit(1);
});
