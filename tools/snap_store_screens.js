// Snap SubZero PWA screenshots for Play Store
// Usage: node tools/snap_store_screens.js
const fs = require('fs');
const path = require('path');

(async () => {
  const puppeteer = await import('puppeteer');
  const url = process.env.SUBZERO_URL || 'https://jhawpetoss6-collab.github.io/subzero/';
  const outDir = path.resolve(__dirname, '..', 'mobile', 'store');
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1080, height: 1920, deviceScaleFactor: 1 });

  async function safeClick(sel) {
    try { await page.waitForSelector(sel, { timeout: 4000 }); await page.click(sel); } catch {}
  }
  async function snap(name) {
    const file = path.join(outDir, name);
    await page.screenshot({ path: file, type: 'png', fullPage: false });
    console.log('Saved', file);
  }

  // Home
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
  await page.waitForTimeout(1200);
  await snap('s1_home_1080x1920.png');

  // Chat
  await safeClick(".chat-card:nth-child(1)");
  await page.waitForTimeout(600);
  await snap('s2_chat_1080x1920.png');

  // Wallet
  await safeClick(".back");
  await page.waitForTimeout(400);
  await safeClick(".chat-card:nth-child(2)");
  await page.waitForTimeout(800);
  await snap('s3_wallet_1080x1920.png');

  // Tap to Pay
  await safeClick("button.wallet-connect-btn"); // the Tap to Pay button
  await page.waitForTimeout(800);
  await snap('s4_tap_to_pay_1080x1920.png');

  // Settings > Income
  await safeClick(".back");
  await page.waitForTimeout(400);
  await safeClick(".back");
  await page.waitForTimeout(400);
  await safeClick(".hamburger");
  await page.waitForTimeout(300);
  await safeClick(".drawer-item:nth-child(6)"); // Settings
  await page.waitForTimeout(700);
  await snap('s5_settings_1080x1920.png');
  // Income screen
  await safeClick(".settings-item:nth-of-type(2)"); // Income Dashboard item we inserted
  await page.waitForTimeout(900);
  await snap('s6_income_1080x1920.png');

  await browser.close();
})();
