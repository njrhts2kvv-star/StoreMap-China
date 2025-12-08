// Parse Louis Vuitton store list from a saved HTML (tmp_lv_list.html) using Playwright.
import fs from "fs";
import { chromium } from "playwright";

const htmlPath = process.argv[2] || "tmp_lv_list.html";

async function main() {
  const html = fs.readFileSync(htmlPath, "utf8");
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
  });
  await page.setContent(html, { waitUntil: "load" });
  const items = await page.evaluate(() => {
    const storeData =
      window.__NUXT__?.data?.["options:asyncdata:StoreLocatorIndex"];
    return storeData?.items || [];
  });
  await browser.close();
  process.stdout.write(JSON.stringify(items));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
