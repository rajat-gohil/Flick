import puppeteer from "puppeteer-core";
import fs from "fs";
import path from "path";

const CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE_URL = "http://localhost:5173";

const SCREENSHOT_DIR = path.resolve("./screenshots/guest_journey");
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function runGuestJourney() {
  console.log("=== FLICK PERSISTENT GUEST BROWSER LIFECYCLE VERIFICATION ===");
  console.log("Launching Chrome from:", CHROME_PATH);

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1280,900"],
    defaultViewport: { width: 1280, height: 900 },
  });

  try {
    // -------------------------------------------------------------
    // Step 1: Onboarding - Start Exploring as Guest
    // -------------------------------------------------------------
    console.log("\n[Step 1] Opening Landing Page as unauthenticated visitor...");
    const context1 = await browser.createBrowserContext();
    const page1 = await context1.newPage();
    await page1.goto(`${BASE_URL}/`, { waitUntil: "networkidle0" });

    console.log("Clicking 'Start Exploring' button...");
    // Find button with text Start Exploring
    const startExploringBtn = await page1.waitForSelector('button ::-p-text("Start Exploring")', { timeout: 8000 });
    if (!startExploringBtn) throw new Error("Could not find 'Start Exploring' button");
    await startExploringBtn.click();

    console.log("Waiting for RecoveryCodeModal to appear...");
    await page1.waitForSelector('[data-testid="recovery-code-display"]', { timeout: 10000 });
    const recoveryCodeEl = await page1.$('[data-testid="recovery-code-display"]');
    const rawCode = await page1.evaluate(el => el.innerText, recoveryCodeEl);
    const cleanRaw = rawCode.replace(/\s+/g, "").replace(/^FLICK/i, "");
    const originalRecoveryCode = (cleanRaw.match(/.{1,4}/g) || [cleanRaw]).join("-");
    console.log(">>> Captured Initial Guest Recovery Code:", originalRecoveryCode);

    // Save screenshot of modal
    await page1.screenshot({ path: path.join(SCREENSHOT_DIR, "01_guest_provision_modal.png") });

    // Check acknowledgment checkbox
    console.log("Checking acknowledgment checkbox...");
    const ackCheckbox = await page1.waitForSelector('input[type="checkbox"]', { timeout: 5000 });
    await ackCheckbox.click();

    // Click continue
    console.log("Clicking 'I've saved my code' button...");
    await page1.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const btn = buttons.find(b => b.innerText.toLowerCase().includes("saved"));
      if (btn) btn.click();
      else throw new Error("Could not find confirm button in modal");
    });

    // Verify redirection to /home
    await page1.waitForFunction(() => window.location.pathname === "/home", { timeout: 8000 });
    console.log("Successfully redirected to /home!");

    // Verify localStorage has auth_token and is_guest === "true", and no raw recovery code
    const storageState1 = await page1.evaluate(() => ({
      authToken: localStorage.getItem("auth_token"),
      isGuest: localStorage.getItem("is_guest"),
      guestUuid: localStorage.getItem("guest_uuid"),
      recoveryCodeInStorage: localStorage.getItem("recovery_code"),
    }));
    console.log("Storage state after onboarding:", storageState1);
    if (!storageState1.authToken) throw new Error("Missing auth_token in localStorage");
    if (storageState1.isGuest !== "true") throw new Error("Expected is_guest === 'true'");
    if (storageState1.recoveryCodeInStorage) throw new Error("CRITICAL: Raw recovery code stored in localStorage!");

    // -------------------------------------------------------------
    // Step 2: Refresh browser & verify guest state persists
    // -------------------------------------------------------------
    console.log("\n[Step 2] Refreshing browser in Context 1...");
    await page1.reload({ waitUntil: "networkidle0" });
    const isStillOnHome = await page1.evaluate(() => window.location.pathname);
    const refreshedStorage = await page1.evaluate(() => ({
      authToken: localStorage.getItem("auth_token"),
      isGuest: localStorage.getItem("is_guest"),
    }));
    console.log("After refresh - Current path:", isStillOnHome, "Storage:", refreshedStorage);
    if (isStillOnHome !== "/home") throw new Error(`Expected /home after reload but got ${isStillOnHome}`);
    if (refreshedStorage.isGuest !== "true") throw new Error("Guest state lost after reload");
    await page1.screenshot({ path: path.join(SCREENSHOT_DIR, "02_guest_home_after_reload.png") });

    // -------------------------------------------------------------
    // Step 3: Restore account in Context 2 using Recovery Code
    // -------------------------------------------------------------
    console.log("\n[Step 3] Launching isolated Browser Context 2 to restore account...");
    const context2 = await browser.createBrowserContext();
    const page2 = await context2.newPage();

    await page2.goto(`${BASE_URL}/recover`, { waitUntil: "networkidle0" });
    console.log("Arrived at /recover page.");

    console.log("Entering recovery code:", originalRecoveryCode);
    const recoverInput = await page2.waitForSelector('input[type="text"]', { timeout: 5000 });
    await recoverInput.type(originalRecoveryCode);

    const restoreBtn = await page2.waitForSelector('button ::-p-text("Restore Journal")', { timeout: 5000 });
    await restoreBtn.click();

    console.log("Waiting for replacement recovery code modal...");
    await page2.waitForSelector('[data-testid="recovery-code-display"]', { timeout: 10000 });
    const replacementCodeEl = await page2.$('[data-testid="recovery-code-display"]');
    const rawReplacementCode = await page2.evaluate(el => el.innerText, replacementCodeEl);
    const replacementCode = rawReplacementCode.replace(/\s+/g, "");
    console.log(">>> Captured Replacement Recovery Code:", replacementCode);
    await page2.screenshot({ path: path.join(SCREENSHOT_DIR, "03_replacement_code_modal.png") });

    if (replacementCode === originalRecoveryCode) {
      throw new Error("Replacement recovery code must differ from original code!");
    }

    // Acknowledge replacement code
    console.log("Checking replacement acknowledgment checkbox...");
    const replaceAckCheckbox = await page2.waitForSelector('input[type="checkbox"]', { timeout: 5000 });
    await replaceAckCheckbox.click();

    console.log("Clicking 'I've saved my replacement code' button...");
    await page2.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const btn = buttons.find(b => b.innerText.toLowerCase().includes("saved"));
      if (btn) btn.click();
      else throw new Error("Could not find confirm button in replacement modal");
    });

    await page2.waitForFunction(() => window.location.pathname === "/home", { timeout: 8000 });
    console.log("Successfully restored and redirected to /home in Context 2!");

    const context2State = await page2.evaluate(() => ({
      authToken: localStorage.getItem("auth_token"),
      isGuest: localStorage.getItem("is_guest"),
      guestUuid: localStorage.getItem("guest_uuid"),
    }));
    console.log("Context 2 Restored Session:", context2State);
    if (context2State.guestUuid !== storageState1.guestUuid) {
      throw new Error(`UUID mismatch! Expected ${storageState1.guestUuid} but got ${context2State.guestUuid}`);
    }

    // -------------------------------------------------------------
    // Step 4: Convert Guest Account to Permanent Account
    // -------------------------------------------------------------
    console.log("\n[Step 4] Navigating to /convert for permanent conversion...");
    await page2.goto(`${BASE_URL}/convert`, { waitUntil: "networkidle0" });

    const testEmail = `cinephile_${Date.now()}@flicktest.local`;
    const testPassword = "ArtHouseCurator2026!";
    console.log(`Filling conversion form with email: ${testEmail}...`);

    const emailInput = await page2.waitForSelector('input[type="email"]', { timeout: 5000 });
    await emailInput.type(testEmail);

    const passwordInputs = await page2.$$('input[type="password"]');
    if (passwordInputs.length < 2) throw new Error("Expected password and confirm password inputs");
    await passwordInputs[0].type(testPassword);
    await passwordInputs[1].type(testPassword);

    await page2.screenshot({ path: path.join(SCREENSHOT_DIR, "04_convert_form_filled.png") });

    console.log("Submitting 'Complete Registration'...");
    const submitConvertBtn = await page2.waitForSelector('button ::-p-text("Complete Registration")', { timeout: 5000 });
    await submitConvertBtn.click();

    console.log("Waiting for conversion completion and navigation to /profile...");
    await page2.waitForFunction(() => window.location.pathname === "/profile", { timeout: 10000 });
    console.log("Successfully arrived at /profile as permanent registered user!");

    const finalStorage = await page2.evaluate(() => ({
      authToken: localStorage.getItem("auth_token"),
      isGuest: localStorage.getItem("is_guest"),
      email: localStorage.getItem("email"),
      guestUuid: localStorage.getItem("guest_uuid"),
    }));
    console.log("Final Storage State after Conversion:", finalStorage);
    if (finalStorage.isGuest !== "false") throw new Error("Expected is_guest === 'false' after conversion");
    if (finalStorage.email !== testEmail) throw new Error(`Expected email ${testEmail} but got ${finalStorage.email}`);
    if (finalStorage.guestUuid !== storageState1.guestUuid) throw new Error("Guest UUID must be preserved across conversion!");

    // Verify profile page does NOT show the guest upgrade banner
    const guestBanner = await page2.$('::-p-text("Guest Member Journal")');
    if (guestBanner) {
      throw new Error("Guest Member Journal banner still present on profile page after conversion!");
    }

    await page2.screenshot({ path: path.join(SCREENSHOT_DIR, "05_converted_profile_page.png") });

    console.log("\n=======================================================");
    console.log("ALL 4 END-TO-END BROWSER LIFECYCLE CHECKS PASSED 100%!");
    console.log("=======================================================");
  } finally {
    await browser.close();
  }
}

runGuestJourney().catch((err) => {
  console.error("Browser journey failed:", err);
  process.exit(1);
});
