import { chromium, request } from "playwright";

const DIRECTORY_URL = process.env.LEGO_DIRECTORY_URL || "https://www.lego.com/zh-cn/stores/directory";
const TARGET_GRAPHQL = "StoresDirectory";

async function fetchDirectory(context) {
  for (let attempt = 1; attempt <= 3; attempt++) {
    const page = await context.newPage();
    let directory = null;

    page.on("response", async (resp) => {
      if (resp.url().includes(TARGET_GRAPHQL)) {
        try {
          directory = await resp.json();
        } catch (_) {
          /* ignore */
        }
      }
    });

    await page.goto(DIRECTORY_URL, { waitUntil: "networkidle", timeout: 150_000 });
    await page.waitForTimeout(5000);
    await page.close();

    if (directory?.data?.storesDirectory) {
      return directory.data.storesDirectory;
    }
    if (attempt === 3) {
      throw new Error("未捕获到 StoresDirectory 数据");
    }
  }
  throw new Error("未捕获到 StoresDirectory 数据");
}

function parseDetailHtml(html) {
  let business = {};
  const matches = html.match(/<script[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi) || [];
  for (const block of matches) {
    const m = block.match(/<script[^>]*>([\s\S]*?)<\/script>/i);
    if (!m) continue;
    try {
      const json = JSON.parse(m[1]);
      if (json && json["@type"] === "LocalBusiness") {
        business = json;
        break;
      }
    } catch (_) {
      /* ignore */
    }
  }

  const address = business.address || {};
  const geo = business.geo || {};
  const nameMatch = html.match(/<h1[^>]*>(.*?)<\/h1>/i);
  const name = business.name || (nameMatch ? nameMatch[1].replace(/<[^>]+>/g, "").trim() : "");
  const phoneMatch = html.match(/Phone[:：]?\\s*([+\\d][\\d\\-\\s]+)/i);
  const googleLinkMatch = html.match(/https?:\/\/[^"']*google[^"']*/i);
  const image = (business.image && business.image.url) || null;

  return {
    name,
    address: address.streetAddress || "",
    city: address.addressLocality || "",
    postalCode: address.postalCode || "",
    latitude: geo.latitude || null,
    longitude: geo.longitude || null,
    phone: business.telephone || (phoneMatch ? phoneMatch[1].trim() : ""),
    googleLink: (business.hasMap || (googleLinkMatch ? googleLinkMatch[0] : "")) || "",
    image,
  };
}

async function fetchStores() {
  const browser = await chromium.launch({
    headless: false,
    args: ["--disable-blink-features=AutomationControlled"],
  });
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    viewport: { width: 1280, height: 720 },
    locale: "zh-CN",
  });

  try {
    const directory = await fetchDirectory(context);
    const filterCountry = process.env.COUNTRY_FILTER;
    const entries = filterCountry
      ? directory.filter((item) => item.country === filterCountry)
      : directory;
    const storeList = [];
    entries.forEach((entry) => {
      (entry.stores || []).forEach((s) =>
        storeList.push({ ...s, country: entry.country, region: entry.region })
      );
    });
    if (!storeList.length) {
      throw new Error("StoresDirectory 无可用门店数据（可能被过滤为空）");
    }

    const storage = await context.storageState();
    const requestCtx = await request.newContext({
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
      storageState: storage,
      locale: "zh-CN",
    });

    const stores = [];
    const limit = process.env.LIMIT ? parseInt(process.env.LIMIT, 10) : null;
    const list = limit ? storeList.slice(0, limit) : storeList;

    const fetchOne = async (store) => {
      if (!store.storeUrl || store.storeUrl.includes("store.default.url")) return null;
      const url = store.storeUrl.startsWith("http")
        ? store.storeUrl
        : `https://www.lego.com${store.storeUrl}`;

      let detail = {};
      for (let i = 0; i < 2; i++) {
        try {
          const resp = await requestCtx.get(url, { timeout: 30_000 });
          const text = await resp.text();
          detail = parseDetailHtml(text);
          break;
        } catch (err) {
          detail = { error: err?.message || String(err) };
          if (i === 1) {
            break;
          }
        }
      }

      return {
        storeId: store.storeId,
        name: store.name,
        phone: detail.phone || store.phone || "",
        address: detail.address || "",
        city: detail.city || "",
        latitude: detail.latitude,
        longitude: detail.longitude,
        googleLink: detail.googleLink || "",
        storeUrl: store.storeUrl,
        urlKey: store.urlKey,
        certified: store.certified,
        additionalInfo: store.additionalInfo,
        image: detail.image || "",
        country: store.country,
        region: store.region,
        raw_detail: detail,
      };
    };

    const concurrency = 20;
    for (let i = 0; i < list.length; i += concurrency) {
      const batch = list.slice(i, i + concurrency);
      const results = await Promise.all(batch.map(fetchOne));
      results.filter(Boolean).forEach((item) => stores.push(item));
    }

    await requestCtx.dispose();
    process.stdout.write(JSON.stringify(stores));
  } finally {
    await browser.close();
  }
}

fetchStores().catch((err) => {
  console.error(err?.stack || err?.message || err);
  process.exit(1);
});
