import { chromium } from "playwright";

const PAGE_URL = "https://www.xiaopeng.com/pengmetta.html";
const TARGET_API = "/api/store/queryAll";

async function fetchStores() {
  const browser = await chromium.launch({ headless: true });
  let payload = null;

  try {
    const context = await browser.newContext({
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    });
    const page = await context.newPage();

    page.on("response", async (resp) => {
      if (resp.url().includes(TARGET_API)) {
        try {
          payload = await resp.json();
        } catch (_) {
          /* ignore */
        }
      }
    });

    await page.goto(PAGE_URL, { waitUntil: "networkidle", timeout: 60_000 });
    await page.waitForTimeout(5_000);

    if (!payload) {
      throw new Error("未捕获到门店数据响应");
    }
    const data = payload?.data;
    if (!Array.isArray(data)) {
      throw new Error("payload 结构异常");
    }
    process.stdout.write(JSON.stringify(data));
  } finally {
    await browser.close();
  }
}

fetchStores().catch((err) => {
  console.error(err?.stack || err?.message || err);
  process.exit(1);
});
