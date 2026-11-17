import puppeteer from "puppeteer-core";
import fs from "fs";
import path from "path";

const CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE_URL = "http://localhost:5173";
const HOST_TOKEN = "8b6d0c68b32aa564ddb72539a3998ec759ada6b0";
const GUEST_TOKEN = "3b72e2319e862070da43ea11a8e09dacc27de9cd";

const SCREENSHOT_DIR = path.resolve("./screenshots");
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function run() {
  console.log("Launching Chrome from:", CHROME_PATH);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1280,900"],
    defaultViewport: { width: 1280, height: 900 },
  });

  try {
    const page = await browser.newPage();

    // ── 1. Host Verification ──
    console.log("1. Navigating as Host (phonetest)...");
    await page.goto(`${BASE_URL}/`, { waitUntil: "networkidle0" });
    await page.evaluate((token) => {
      localStorage.setItem("auth_token", token);
      localStorage.setItem("username", "phonetest");
    }, HOST_TOKEN);

    await page.goto(`${BASE_URL}/sessions`, { waitUntil: "networkidle0" });
    await page.waitForSelector('[data-testid^="end-room-btn-"]', { timeout: 10000 });

    const hostBtn = await page.$('[data-testid^="end-room-btn-"]');
    const hostBtnText = await page.evaluate((el) => el.innerText, hostBtn);
    console.log("Host sees button:", hostBtnText);

    const hostScreenshotPath = path.join(SCREENSHOT_DIR, "01_host_active_sessions.png");
    await page.screenshot({ path: hostScreenshotPath, fullPage: true });
    console.log("Saved screenshot:", hostScreenshotPath);

    // ── 2. Guest Verification ──
    console.log("2. Navigating as Guest (amita)...");
    await page.evaluate((token) => {
      localStorage.setItem("auth_token", token);
      localStorage.setItem("username", "amita");
    }, GUEST_TOKEN);

    await page.goto(`${BASE_URL}/sessions`, { waitUntil: "networkidle0" });
    await page.waitForSelector('[data-testid^="end-room-btn-"]', { timeout: 10000 });

    const guestBtn = await page.$('[data-testid^="end-room-btn-"]');
    const guestBtnText = await page.evaluate((el) => el.innerText, guestBtn);
    console.log("Guest sees button with equal permission:", guestBtnText);

    const guestScreenshotPath = path.join(SCREENSHOT_DIR, "02_guest_active_sessions.png");
    await page.screenshot({ path: guestScreenshotPath, fullPage: true });
    console.log("Saved screenshot:", guestScreenshotPath);

    // ── 3. Guest Confirmation Dialog ──
    console.log("3. Guest clicks 'End Room' button...");
    await guestBtn.click();

    await page.waitForSelector('[data-testid="archive-end-confirm-modal"]', { timeout: 5000 });
    const modalText = await page.evaluate(() => {
      const modal = document.querySelector('[data-testid="archive-end-confirm-modal"]');
      return modal ? modal.innerText : "";
    });
    console.log("Confirmation modal content:\n", modalText);

    const modalScreenshotPath = path.join(SCREENSHOT_DIR, "03_guest_confirmation_modal.png");
    await page.screenshot({ path: modalScreenshotPath, fullPage: true });
    console.log("Saved screenshot:", modalScreenshotPath);

    // ── 4. Guest Confirms Termination ──
    console.log("4. Guest confirms room termination...");
    const proceedBtn = await page.$('[data-testid="archive-end-confirm-proceed-btn"]');
    await proceedBtn.click();

    // Wait for modal to disappear and directory to refresh
    await page.waitForFunction(() => !document.querySelector('[data-testid="archive-end-confirm-modal"]'), { timeout: 5000 });
    await new Promise((r) => setTimeout(r, 1500));

    const postEndScreenshotPath = path.join(SCREENSHOT_DIR, "04_guest_after_termination.png");
    await page.screenshot({ path: postEndScreenshotPath, fullPage: true });
    console.log("Saved screenshot:", postEndScreenshotPath);

    console.log("SUCCESS: End Room button verified in real browser for both Host and Guest!");
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error("Browser verification failed:", err);
  process.exit(1);
});
