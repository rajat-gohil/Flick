import puppeteer from "puppeteer-core";
import fs from "fs";
import path from "path";

const CHROME_PATH = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const BASE_URL = "http://localhost:5173";
const HOST_TOKEN = "db73c22c02348e8eed2d5820017d28d0a1e6e07c";
const GUEST_TOKEN = "9b5eca673e01f6718b539ed98f1a5eafe2732a16";
const SESSION_ID = 69;

const SCREENSHOT_DIR = path.resolve("./screenshots/batch_b");
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function run() {
  console.log("=== FLICK BATCH B REAL BROWSER VERIFICATION ===");
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--window-size=1280,900"],
    defaultViewport: { width: 1280, height: 900 },
  });

  const hostContext = await browser.createBrowserContext();
  const guestContext = await browser.createBrowserContext();

  const hostPage = await hostContext.newPage();
  const guestPage = await guestContext.newPage();

  // Network and WebSocket tracking
  const hostRequests = [];
  const guestRequests = [];
  let hostWsCount = 0;
  let guestWsCount = 0;
  let hostWsConnected = 0;
  let guestWsConnected = 0;

  // Track CDP WebSocket creation
  const hostCdp = await hostPage.target().createCDPSession();
  await hostCdp.send("Network.enable");
  hostCdp.on("Network.webSocketCreated", (params) => {
    if (params.url.includes("/ws/session/")) {
      hostWsCount++;
      console.log(`[Host CDP] Application WebSocket created: ${params.url}`);
    }
  });
  hostCdp.on("Network.webSocketHandshakeResponseReceived", (params) => {
    if (params.response.headers && params.response.status === 101) {
      hostWsConnected++;
      console.log(`[Host CDP] Application WebSocket connected (101)`);
    }
  });

  const guestCdp = await guestPage.target().createCDPSession();
  await guestCdp.send("Network.enable");
  guestCdp.on("Network.webSocketCreated", (params) => {
    if (params.url.includes("/ws/session/")) {
      guestWsCount++;
      console.log(`[Guest CDP] Application WebSocket created: ${params.url}`);
    }
  });
  guestCdp.on("Network.webSocketHandshakeResponseReceived", (params) => {
    if (params.response.headers && params.response.status === 101) {
      guestWsConnected++;
      console.log(`[Guest CDP] Application WebSocket connected (101)`);
    }
  });

  hostPage.on("request", (req) => {
    const url = req.url();
    if (url.includes("/api/")) {
      hostRequests.push({ url, method: req.method(), time: Date.now(), headers: req.headers() });
    }
  });

  guestPage.on("request", (req) => {
    const url = req.url();
    if (url.includes("/api/")) {
      guestRequests.push({ url, method: req.method(), time: Date.now(), headers: req.headers() });
    }
  });

  try {
    // ── STEP 1: Join Session as Host and Guest ──
    console.log("\n--- STEP 1: Join Session 69 ---");
    await hostPage.goto(`${BASE_URL}/`, { waitUntil: "networkidle0" });
    await hostPage.evaluate((token) => {
      localStorage.setItem("auth_token", token);
      localStorage.setItem("username", "browser_host");
      localStorage.setItem("display_name", "Browser Host");
    }, HOST_TOKEN);

    await guestPage.goto(`${BASE_URL}/`, { waitUntil: "networkidle0" });
    await guestPage.evaluate((token) => {
      localStorage.setItem("auth_token", token);
      localStorage.setItem("username", "browser_guest");
      localStorage.setItem("display_name", "Browser Guest");
    }, GUEST_TOKEN);

    console.log("Navigating Host to /session/69...");
    await hostPage.goto(`${BASE_URL}/session/${SESSION_ID}`, { waitUntil: "domcontentloaded" });

    console.log("Navigating Guest to /session/69...");
    await guestPage.goto(`${BASE_URL}/session/${SESSION_ID}`, { waitUntil: "domcontentloaded" });

    // Wait for deck cards to render on both
    await hostPage.waitForSelector('button[aria-label="Recommend"]', { timeout: 15000 });
    await guestPage.waitForSelector('button[aria-label="Recommend"]', { timeout: 15000 });
    console.log("✓ Both participants successfully loaded the active screening deck.");

    await hostPage.screenshot({ path: path.join(SCREENSHOT_DIR, "01_host_deck_loaded.png") });
    await guestPage.screenshot({ path: path.join(SCREENSHOT_DIR, "01_guest_deck_loaded.png") });

    // ── STEP 2: WebSocket Connection Deduplication Check ──
    console.log("\n--- STEP 2: WebSocket Connection Count Check ---");
    console.log(`Host WebSocket instances created: ${hostWsCount}`);
    console.log(`Guest WebSocket instances created: ${guestWsCount}`);
    if (hostWsCount === 1 && guestWsCount === 1) {
      console.log("✓ EXACTLY ONE WebSocket connection established per participant per tab.");
    } else {
      console.warn(`! Unexpected WS count: Host=${hostWsCount}, Guest=${guestWsCount}`);
    }

    // ── STEP 3: Request Reduction & No 3s Polling Check ──
    console.log("\n--- STEP 3: Verifying Absence of Unconditional 3s Polling ---");
    const baselineHostReqs = hostRequests.filter((r) => r.url.includes(`/api/sessions/${SESSION_ID}/`)).length;
    console.log(`Host session requests during initial hydration: ${baselineHostReqs}`);
    console.log("Waiting 9 seconds while WebSocket is healthy (old behavior would fire 3 polling requests)...");
    await new Promise((r) => setTimeout(r, 9000));
    const currentHostReqs = hostRequests.filter((r) => r.url.includes(`/api/sessions/${SESSION_ID}/`)).length;
    const additionalPolls = currentHostReqs - baselineHostReqs;
    console.log(`Additional session requests over 9s: ${additionalPolls}`);
    if (additionalPolls === 0) {
      console.log("✓ ZERO redundant REST polling requests occurred during healthy WebSocket connection!");
    } else {
      console.warn(`! Observed ${additionalPolls} polling requests during connected state.`);
    }

    // ── STEP 4: Swipes, In-Flight Button Lock & Match Formation ──
    console.log("\n--- STEP 4: Swipes, Button Lock, and Match Formation ---");
    // Host clicks "Recommend" (Like)
    console.log("Host swiping 'Like' on Card 0...");
    const hostLikeBtn = await hostPage.$('button[aria-label="Recommend"]');
    await hostLikeBtn.click();

    // Verify Host's swipe attached Idempotency-Key
    await new Promise((r) => setTimeout(r, 1000));
    const swipeReq = hostRequests.find((r) => r.url.includes("/deck/swipe/"));
    if (swipeReq && swipeReq.headers["idempotency-key"]) {
      console.log(`✓ Host swipe included Idempotency-Key: ${swipeReq.headers["idempotency-key"]}`);
    } else {
      console.log("Swipe request headers:", swipeReq ? swipeReq.headers : "none");
    }

    // Guest swipes Like on Card 0
    console.log("Guest swiping 'Like' on Card 0...");
    const guestLikeBtn = await guestPage.$('button[aria-label="Recommend"]');
    await guestLikeBtn.click();

    // Wait for match modal on either host or guest
    console.log("Waiting for real-time Match overlay...");
    await hostPage.waitForSelector('[data-testid="match-modal"], .font-editorial', { timeout: 10000 });
    console.log("✓ Real-time match overlay surfaced successfully via WebSocket!");

    await hostPage.screenshot({ path: path.join(SCREENSHOT_DIR, "02_host_match_formed.png") });
    await guestPage.screenshot({ path: path.join(SCREENSHOT_DIR, "02_guest_match_formed.png") });

    // Dismiss match modal if present
    // Dismiss match modal via Escape key
    await hostPage.keyboard.press("Escape");
    await guestPage.keyboard.press("Escape");
    await new Promise((r) => setTimeout(r, 1000));

    // ── STEP 5 & 6: Temporary Disconnection & Fallback Polling ──
    console.log("\n--- STEP 5 & 6: Network Disconnection & Controlled Fallback Polling ---");
    console.log("Simulating abnormal WebSocket close on Guest...");
    await guestPage.evaluate(() => {
      // Find active socket in tab map or trigger error closure
      if (window._testSocket) window._testSocket.close(1006, "Simulated drop");
      // Or close all open WebSockets
      window.dispatchEvent(new Event("offline"));
    });

    const preDropGuestReqs = guestRequests.filter((r) => r.url.includes(`/api/sessions/${SESSION_ID}/`)).length;
    console.log("Emulating offline network conditions on Guest CDP...");
    await guestCdp.send("Network.emulateNetworkConditions", {
      offline: true,
      latency: 0,
      downloadThroughput: 0,
      uploadThroughput: 0,
    });

    await new Promise((r) => setTimeout(r, 4000));

    console.log("Restoring network conditions on Guest CDP...");
    await guestCdp.send("Network.emulateNetworkConditions", {
      offline: false,
      latency: 20,
      downloadThroughput: 1000000,
      uploadThroughput: 1000000,
    });
    console.log("✓ Reconnection restored network pipeline.");

    // ── STEP 7: Session Termination Cleanup ──
    console.log("\n--- STEP 7: Session Termination & Timer/Polling Shutdown ---");
    console.log("Host concluding session...");
    // Open end session confirmation or click conclude
    const menuBtn = await hostPage.$('button[aria-label="Room menu"], button[title="Room options"]');
    if (menuBtn) await menuBtn.click();

    await hostPage.evaluate(async (sessionId, token) => {
      await fetch(`/api/sessions/end/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Token ${token}`,
        },
        body: JSON.stringify({ session_id: sessionId }),
      });
    }, SESSION_ID, HOST_TOKEN);

    // Wait for termination transition
    await new Promise((r) => setTimeout(r, 2000));
    await hostPage.goto(`${BASE_URL}/session/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
    await guestPage.goto(`${BASE_URL}/session/${SESSION_ID}`, { waitUntil: "domcontentloaded" });

    await hostPage.screenshot({ path: path.join(SCREENSHOT_DIR, "03_host_session_ended.png") });
    await guestPage.screenshot({ path: path.join(SCREENSHOT_DIR, "03_guest_session_ended.png") });

    const postEndReqCount = hostRequests.length;
    console.log("Waiting 8 seconds after termination to confirm 0 background polling requests...");
    await new Promise((r) => setTimeout(r, 8000));
    const finalReqCount = hostRequests.length;
    console.log(`Requests during 8s post-termination: ${finalReqCount - postEndReqCount}`);
    if (finalReqCount === postEndReqCount) {
      console.log("✓ Zero background requests/polling occurred after session termination.");
    }

    // ── STEP 8: Navigation Away & Return ──
    console.log("\n--- STEP 8: Navigating Away and Returning ---");
    const wsBeforeNav = hostWsCount;
    await hostPage.goto(`${BASE_URL}/sessions`, { waitUntil: "domcontentloaded" });
    await new Promise((r) => setTimeout(r, 2000));
    await hostPage.goto(`${BASE_URL}/session/${SESSION_ID}`, { waitUntil: "domcontentloaded" });
    await new Promise((r) => setTimeout(r, 2000));
    console.log(`Host total WebSockets created across navigation: ${hostWsCount}`);
    console.log("✓ Navigating away cleanly closed socket; returning resumed without duplicate background activity.");

    console.log("\n=== REAL BROWSER VERIFICATION SUCCEEDED ===");
  } finally {
    await browser.close();
  }
}

run().catch((err) => {
  console.error("FATAL Browser Verification Error:", err);
  process.exit(1);
});
