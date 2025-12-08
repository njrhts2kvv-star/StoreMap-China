import { chromium } from "playwright";

const PAGE_URL =
  process.env.TESLA_PAGE_URL ||
  "https://www.tesla.cn/findus?bounds=40.11393476927143%2C116.77453305675563%2C39.715481225762645%2C116.03346694324422";
const LIST_KEYWORD = "get-locations?country=CN&view=list&functionType=tesla_center_sales";

async function fetchLocations() {
  const browser = await chromium.launch({
    headless: false,
    args: ["--disable-blink-features=AutomationControlled"],
  });

  let payload = null;

  try {
    const context = await browser.newContext({
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
      locale: "zh-CN",
      viewport: { width: 1280, height: 720 },
    });
    const page = await context.newPage();

    page.on("response", async (resp) => {
      const url = resp.url();
      if (url.includes(LIST_KEYWORD)) {
        try {
          payload = await resp.json();
        } catch (_) {
          /* ignore */
        }
      }
    });

    await page.goto(PAGE_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
    await page.waitForTimeout(10_000);

    if (!payload) {
      throw new Error("list payload not captured");
    }
    const data = payload?.data?.data;
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
