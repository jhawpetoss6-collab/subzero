// Generate Play Store screenshots 1080×1920 for SubZero
const { createCanvas, loadImage } = require('canvas');
const QRCode = require('qrcode');
const fs = require('fs');
const path = require('path');

const W = 1080, H = 1920;
const outDir = path.resolve(__dirname, '..', 'mobile', 'store', 'screens', 'processed');
fs.mkdirSync(outDir, { recursive: true });

const BG = '#0a0e14';
const ACCENT = '#00e5a0';
const FG = '#e6edf3';
const DIM = '#8b949e';
const CARD_BG = '#161b22';
const BORDER = '#30363d';

function save(canvas, name) {
  const buf = canvas.toBuffer('image/png');
  const p = path.join(outDir, name);
  fs.writeFileSync(p, buf);
  console.log('Wrote', p, (buf.length / 1024).toFixed(0) + 'KB');
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawStatusBar(ctx) {
  ctx.fillStyle = DIM;
  ctx.font = '28px sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText('9:41', 40, 52);
  ctx.textAlign = 'right';
  ctx.fillText('100%  ▮', W - 40, 52);
  ctx.textAlign = 'left';
}

function drawBottomNav(ctx, active) {
  const y = H - 110;
  ctx.fillStyle = CARD_BG;
  ctx.fillRect(0, y, W, 110);
  ctx.strokeStyle = BORDER;
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  const tabs = ['💬 Chats', '👤 Contacts', '🔔 Alerts', '⚙️ Settings'];
  const tw = W / tabs.length;
  tabs.forEach((t, i) => {
    ctx.fillStyle = (i === active) ? ACCENT : DIM;
    ctx.font = '26px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(t, tw * i + tw / 2, y + 65);
  });
  ctx.textAlign = 'left';
}

// ─── Screen 1: Home / Chat List ───
function genHomeScreen() {
  const c = createCanvas(W, H);
  const ctx = c.getContext('2d');
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  drawStatusBar(ctx);

  // Header
  ctx.fillStyle = ACCENT;
  ctx.font = 'bold 44px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('SUB-ZERO', W / 2, 130);
  ctx.fillStyle = DIM;
  ctx.font = '24px sans-serif';
  ctx.fillText('Flawless Victory', W / 2, 170);
  ctx.textAlign = 'left';

  // Search bar
  roundRect(ctx, 50, 210, W - 100, 60, 16);
  ctx.fillStyle = CARD_BG; ctx.fill();
  ctx.strokeStyle = BORDER; ctx.lineWidth = 1.5; ctx.stroke();
  ctx.fillStyle = DIM; ctx.font = '26px sans-serif';
  ctx.fillText('🔍  Search conversations...', 80, 250);

  // Chat cards
  const chats = [
    { name: 'Spine Rip AI', msg: 'How can I assist you today?', time: '2:30 PM', unread: 3 },
    { name: 'Crypto Wallet', msg: 'SOL balance: 12.5 SOL', time: '1:15 PM', unread: 0 },
    { name: 'Payment Hub', msg: 'Tap-to-Pay ready ✓', time: '12:00 PM', unread: 1 },
    { name: 'Alice Johnson', msg: 'Sent you $25.00 via Cash App', time: '11:30 AM', unread: 0 },
    { name: 'Dev Team', msg: 'Build v2.5 deployed 🚀', time: '10:00 AM', unread: 5 },
    { name: 'Bob Smith', msg: 'QR payment received!', time: '9:45 AM', unread: 0 },
    { name: 'SubZero Updates', msg: 'New features available', time: 'Yesterday', unread: 2 },
  ];

  let y = 300;
  chats.forEach(ch => {
    roundRect(ctx, 30, y, W - 60, 110, 16);
    ctx.fillStyle = CARD_BG; ctx.fill();
    ctx.strokeStyle = BORDER; ctx.lineWidth = 1; ctx.stroke();

    // Avatar circle
    ctx.fillStyle = ACCENT;
    ctx.beginPath(); ctx.arc(90, y + 55, 30, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = BG; ctx.font = 'bold 26px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(ch.name[0], 90, y + 64); ctx.textAlign = 'left';

    ctx.fillStyle = FG; ctx.font = 'bold 30px sans-serif';
    ctx.fillText(ch.name, 140, y + 42);
    ctx.fillStyle = DIM; ctx.font = '24px sans-serif';
    ctx.fillText(ch.msg, 140, y + 78);

    ctx.fillStyle = DIM; ctx.font = '22px sans-serif'; ctx.textAlign = 'right';
    ctx.fillText(ch.time, W - 55, y + 40); ctx.textAlign = 'left';

    if (ch.unread) {
      ctx.fillStyle = ACCENT;
      ctx.beginPath(); ctx.arc(W - 70, y + 75, 18, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = BG; ctx.font = 'bold 20px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText(ch.unread, W - 70, y + 82); ctx.textAlign = 'left';
    }
    y += 130;
  });

  // FAB
  ctx.fillStyle = ACCENT;
  ctx.beginPath(); ctx.arc(W - 90, H - 200, 36, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = BG; ctx.font = 'bold 40px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('+', W - 90, H - 188); ctx.textAlign = 'left';

  drawBottomNav(ctx, 0);
  save(c, 's1_home_1080x1920.png');
}

// ─── Screen 2: Chat / AI Conversation ───
function genChatScreen() {
  const c = createCanvas(W, H);
  const ctx = c.getContext('2d');
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  drawStatusBar(ctx);

  // Header bar
  ctx.fillStyle = CARD_BG; ctx.fillRect(0, 70, W, 80);
  ctx.strokeStyle = BORDER; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(0, 150); ctx.lineTo(W, 150); ctx.stroke();
  ctx.fillStyle = FG; ctx.font = '22px sans-serif'; ctx.fillText('← Back', 30, 118);
  ctx.fillStyle = ACCENT; ctx.font = 'bold 34px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('Spine Rip AI', W / 2, 122);
  ctx.fillStyle = DIM; ctx.font = '22px sans-serif'; ctx.fillText('⋮', W - 40, 118);
  ctx.textAlign = 'left';

  // Messages
  const msgs = [
    { from: 'ai', text: 'Welcome to SubZero! I\'m Spine Rip, your AI assistant. How can I help?' },
    { from: 'user', text: 'Show me my crypto wallet balance' },
    { from: 'ai', text: '💰 Your Balances:\n• SOL: 12.500\n• ETH: 0.850\n• USDC: 250.00\nTotal ≈ $3,420.50' },
    { from: 'user', text: 'Send 0.5 SOL to my friend' },
    { from: 'ai', text: '✅ Transaction prepared:\n→ 0.5 SOL to 7xKp...3mNq\nFee: 0.000005 SOL\nConfirm in your wallet to proceed.' },
    { from: 'user', text: 'What about payment options?' },
    { from: 'ai', text: '💳 Available payment methods:\n• Cash App  •  Venmo\n• Google Pay  •  Crypto\n• QR Code scan\nTap "Pay" in the wallet to start!' },
  ];

  let y = 180;
  msgs.forEach(m => {
    const isUser = m.from === 'user';
    const maxW = W * 0.7;
    ctx.font = '26px sans-serif';
    const lines = m.text.split('\n');
    const lh = 34;
    const bh = lines.length * lh + 28;
    const bw = Math.min(maxW, Math.max(...lines.map(l => ctx.measureText(l).width)) + 40);
    const bx = isUser ? W - bw - 40 : 40;

    roundRect(ctx, bx, y, bw, bh, 18);
    ctx.fillStyle = isUser ? '#1a3a2a' : CARD_BG; ctx.fill();
    ctx.strokeStyle = isUser ? ACCENT : BORDER; ctx.lineWidth = 1; ctx.stroke();

    ctx.fillStyle = isUser ? '#c3f5d9' : FG;
    ctx.font = '26px sans-serif';
    lines.forEach((l, i) => {
      ctx.fillText(l, bx + 20, y + 30 + i * lh);
    });
    y += bh + 16;
  });

  // Input bar
  const iy = H - 130;
  ctx.fillStyle = CARD_BG; ctx.fillRect(0, iy, W, 130);
  roundRect(ctx, 30, iy + 20, W - 160, 55, 28);
  ctx.fillStyle = '#0d1117'; ctx.fill();
  ctx.strokeStyle = BORDER; ctx.lineWidth = 1; ctx.stroke();
  ctx.fillStyle = DIM; ctx.font = '24px sans-serif';
  ctx.fillText('Message Spine Rip...', 60, iy + 55);

  ctx.fillStyle = ACCENT;
  ctx.beginPath(); ctx.arc(W - 65, iy + 47, 28, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = BG; ctx.font = 'bold 28px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('➤', W - 65, iy + 56); ctx.textAlign = 'left';

  save(c, 's2_chat_1080x1920.png');
}

// ─── Screen 3: Tap-to-Pay / Payment Hub ───
function genPayScreen() {
  const c = createCanvas(W, H);
  const ctx = c.getContext('2d');
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  drawStatusBar(ctx);

  ctx.fillStyle = CARD_BG; ctx.fillRect(0, 70, W, 80);
  ctx.fillStyle = ACCENT; ctx.font = 'bold 36px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('⚡ Tap-to-Pay', W / 2, 122);
  ctx.textAlign = 'left';

  // Amount display
  let y = 200;
  roundRect(ctx, 60, y, W - 120, 160, 20);
  ctx.fillStyle = CARD_BG; ctx.fill();
  ctx.strokeStyle = ACCENT; ctx.lineWidth = 2; ctx.stroke();
  ctx.fillStyle = DIM; ctx.font = '26px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('Amount', W / 2, y + 40);
  ctx.fillStyle = ACCENT; ctx.font = 'bold 72px sans-serif';
  ctx.fillText('$25.00', W / 2, y + 115);
  ctx.fillStyle = DIM; ctx.font = '22px sans-serif';
  ctx.fillText('Fee: $1.03  •  Total: $26.03', W / 2, y + 148);
  ctx.textAlign = 'left';

  // Payment method buttons
  y = 400;
  const methods = [
    { icon: '💵', name: 'Cash App', color: '#00D632' },
    { icon: '💙', name: 'Venmo', color: '#3D95CE' },
    { icon: '🔷', name: 'Google Pay', color: '#4285F4' },
    { icon: '🪙', name: 'Crypto (SOL)', color: '#9945FF' },
    { icon: '📱', name: 'Scan QR Code', color: ACCENT },
  ];
  methods.forEach(m => {
    roundRect(ctx, 60, y, W - 120, 80, 16);
    ctx.fillStyle = CARD_BG; ctx.fill();
    ctx.strokeStyle = m.color; ctx.lineWidth = 1.5; ctx.stroke();

    ctx.font = '32px sans-serif'; ctx.fillStyle = FG;
    ctx.fillText(m.icon + '  ' + m.name, 100, y + 52);

    ctx.fillStyle = m.color; ctx.textAlign = 'right'; ctx.font = '26px sans-serif';
    ctx.fillText('Select →', W - 85, y + 52); ctx.textAlign = 'left';
    y += 100;
  });

  // QR preview
  y += 20;
  roundRect(ctx, 60, y, W - 120, 380, 20);
  ctx.fillStyle = CARD_BG; ctx.fill();
  ctx.strokeStyle = BORDER; ctx.lineWidth = 1; ctx.stroke();

  ctx.fillStyle = ACCENT; ctx.font = 'bold 28px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('Your Payment QR', W / 2, y + 45);

  // Fake QR placeholder
  const qSize = 240;
  const qx = (W - qSize) / 2, qy = y + 65;
  ctx.fillStyle = '#fff';
  ctx.fillRect(qx, qy, qSize, qSize);
  // Draw a simple grid pattern to simulate QR
  ctx.fillStyle = '#000';
  for (let r = 0; r < 20; r++) {
    for (let col = 0; col < 20; col++) {
      if ((r + col) % 3 === 0 || (r * col) % 7 < 3) {
        ctx.fillRect(qx + col * 12, qy + r * 12, 12, 12);
      }
    }
  }
  // Corner squares
  [[qx, qy], [qx + qSize - 42, qy], [qx, qy + qSize - 42]].forEach(([cx, cy]) => {
    ctx.fillStyle = '#000'; ctx.fillRect(cx, cy, 42, 42);
    ctx.fillStyle = '#fff'; ctx.fillRect(cx + 6, cy + 6, 30, 30);
    ctx.fillStyle = '#000'; ctx.fillRect(cx + 12, cy + 12, 18, 18);
  });

  ctx.fillStyle = DIM; ctx.font = '22px sans-serif';
  ctx.fillText('Show this to receive payment', W / 2, y + 365);
  ctx.textAlign = 'left';

  drawBottomNav(ctx, -1);
  save(c, 's3_pay_1080x1920.png');
}

// ─── Screen 4: Scan to Download (matches user's screenshot) ───
async function genScanToDownload() {
  const c = createCanvas(W, H);
  const ctx = c.getContext('2d');

  // Dark background with subtle border
  ctx.fillStyle = '#050810'; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = '#00c8ff';
  ctx.lineWidth = 4;
  roundRect(ctx, 30, 30, W - 60, H - 60, 16);
  ctx.stroke();

  // Logo placeholder (small square icon)
  const logoSize = 60;
  const lx = (W - logoSize) / 2, ly = 140;
  ctx.strokeStyle = ACCENT; ctx.lineWidth = 3;
  ctx.strokeRect(lx, ly, logoSize, logoSize);
  ctx.fillStyle = ACCENT;
  ctx.fillRect(lx + 18, ly + 18, 24, 24);

  // Title
  ctx.fillStyle = FG; ctx.font = 'bold 64px sans-serif'; ctx.textAlign = 'center';
  ctx.letterSpacing = '12px';
  ctx.fillText('S U B - Z E R O', W / 2, 310);
  ctx.letterSpacing = '0px';

  // Subtitle
  ctx.fillStyle = ACCENT; ctx.font = 'bold 30px sans-serif';
  ctx.fillText('F L A W L E S S    V I C T O R Y', W / 2, 380);

  ctx.fillStyle = DIM; ctx.font = '26px sans-serif';
  ctx.fillText('Autonomous AI Runtime', W / 2, 430);

  // Generate real QR code
  const qrURL = 'https://jhawpetoss6-collab.github.io/subzero/';
  const qrCanvas = createCanvas(600, 600);
  await QRCode.toCanvas(qrCanvas, qrURL, {
    width: 600,
    color: { dark: '#00c8ff', light: '#050810' },
    errorCorrectionLevel: 'H'
  });
  ctx.drawImage(qrCanvas, (W - 600) / 2, 520, 600, 600);

  // "Scan to Download" label
  ctx.fillStyle = FG; ctx.font = 'bold 38px sans-serif';
  ctx.fillText('Scan to Download', W / 2, 1210);

  ctx.fillStyle = DIM; ctx.font = '24px sans-serif';
  ctx.fillText('Share Sub-Zero with anyone', W / 2, 1260);

  // Version
  ctx.fillStyle = DIM; ctx.font = '22px sans-serif';
  ctx.fillText('v2.5', W / 2, H - 80);
  ctx.textAlign = 'left';

  save(c, 's4_download_1080x1920.png');
}

// ─── Screen 5: Settings / Income Dashboard ───
function genSettingsScreen() {
  const c = createCanvas(W, H);
  const ctx = c.getContext('2d');
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  drawStatusBar(ctx);

  ctx.fillStyle = CARD_BG; ctx.fillRect(0, 70, W, 80);
  ctx.fillStyle = ACCENT; ctx.font = 'bold 36px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('⚙️ Settings', W / 2, 122);
  ctx.textAlign = 'left';

  let y = 190;
  const items = [
    { icon: '👤', label: 'Account', desc: 'Profile, security, linked accounts' },
    { icon: '💰', label: 'Income Dashboard', desc: 'Track platform fee earnings' },
    { icon: '🔗', label: 'Linked Payments', desc: 'Cash App, Venmo, Google Pay' },
    { icon: '🪙', label: 'Crypto Wallets', desc: 'SOL, ETH, USDC addresses' },
    { icon: '🔔', label: 'Notifications', desc: 'Alerts, sounds, badge count' },
    { icon: '🎨', label: 'Appearance', desc: 'Theme, font size, layout' },
    { icon: '🛡️', label: 'Privacy & Security', desc: 'Data, permissions, 2FA' },
    { icon: '📱', label: 'About SubZero', desc: 'Version 2.5 • Build 2026.02' },
  ];
  items.forEach(it => {
    roundRect(ctx, 30, y, W - 60, 100, 14);
    ctx.fillStyle = CARD_BG; ctx.fill();
    ctx.strokeStyle = BORDER; ctx.lineWidth = 1; ctx.stroke();

    ctx.font = '36px sans-serif'; ctx.fillStyle = FG;
    ctx.fillText(it.icon, 60, y + 60);
    ctx.font = 'bold 28px sans-serif'; ctx.fillStyle = FG;
    ctx.fillText(it.label, 120, y + 44);
    ctx.font = '22px sans-serif'; ctx.fillStyle = DIM;
    ctx.fillText(it.desc, 120, y + 78);

    ctx.fillStyle = DIM; ctx.textAlign = 'right'; ctx.font = '28px sans-serif';
    ctx.fillText('›', W - 50, y + 58); ctx.textAlign = 'left';
    y += 118;
  });

  drawBottomNav(ctx, 3);
  save(c, 's5_settings_1080x1920.png');
}

// ─── Screen 6: Income Dashboard ───
function genIncomeScreen() {
  const c = createCanvas(W, H);
  const ctx = c.getContext('2d');
  ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
  drawStatusBar(ctx);

  ctx.fillStyle = CARD_BG; ctx.fillRect(0, 70, W, 80);
  ctx.fillStyle = FG; ctx.font = '22px sans-serif'; ctx.fillText('← Settings', 30, 118);
  ctx.fillStyle = ACCENT; ctx.font = 'bold 34px sans-serif'; ctx.textAlign = 'center';
  ctx.fillText('💰 Income Dashboard', W / 2, 122);
  ctx.textAlign = 'left';

  // Summary cards
  let y = 190;
  const summaries = [
    { label: 'Total Earned', value: '$1,247.83', color: ACCENT },
    { label: 'This Month', value: '$342.50', color: '#3D95CE' },
    { label: 'Transactions', value: '156', color: '#9945FF' },
  ];
  const cw = (W - 90) / 3;
  summaries.forEach((s, i) => {
    const cx = 30 + i * (cw + 15);
    roundRect(ctx, cx, y, cw, 130, 14);
    ctx.fillStyle = CARD_BG; ctx.fill();
    ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.stroke();

    ctx.fillStyle = DIM; ctx.font = '20px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(s.label, cx + cw / 2, y + 40);
    ctx.fillStyle = s.color; ctx.font = 'bold 32px sans-serif';
    ctx.fillText(s.value, cx + cw / 2, y + 90);
  });
  ctx.textAlign = 'left';

  // Chart area
  y = 360;
  roundRect(ctx, 30, y, W - 60, 300, 16);
  ctx.fillStyle = CARD_BG; ctx.fill();
  ctx.strokeStyle = BORDER; ctx.lineWidth = 1; ctx.stroke();

  ctx.fillStyle = FG; ctx.font = 'bold 24px sans-serif';
  ctx.fillText('Weekly Earnings', 60, y + 40);

  // Simple bar chart
  const bars = [65, 42, 88, 55, 73, 95, 60];
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const bw = 80, gap = (W - 120 - bars.length * bw) / (bars.length - 1);
  const maxBar = 200, baseY = y + 270;
  bars.forEach((v, i) => {
    const bx = 60 + i * (bw + gap);
    const bh = (v / 100) * maxBar;
    roundRect(ctx, bx, baseY - bh, bw, bh, 8);
    ctx.fillStyle = ACCENT; ctx.globalAlpha = 0.3 + 0.7 * (v / 100); ctx.fill();
    ctx.globalAlpha = 1;
    ctx.fillStyle = DIM; ctx.font = '18px sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(days[i], bx + bw / 2, baseY + 24);
  });
  ctx.textAlign = 'left';

  // Recent transactions
  y = 690;
  ctx.fillStyle = FG; ctx.font = 'bold 28px sans-serif';
  ctx.fillText('Recent Fee Income', 40, y);
  y += 20;

  const txns = [
    { method: '💵 Cash App', from: 'Alice → Bob', fee: '$1.03', time: '2:30 PM' },
    { method: '💙 Venmo', from: 'Charlie → Dana', fee: '$0.88', time: '1:15 PM' },
    { method: '🪙 SOL', from: 'Eve → Frank', fee: '$2.15', time: '12:00 PM' },
    { method: '💵 Cash App', from: 'Grace → Hank', fee: '$0.59', time: '11:30 AM' },
    { method: '🔷 Google Pay', from: 'Ivy → Jack', fee: '$1.47', time: '10:00 AM' },
    { method: '💙 Venmo', from: 'Kate → Leo', fee: '$3.21', time: '9:45 AM' },
    { method: '🪙 ETH', from: 'Mia → Nick', fee: '$4.50', time: '9:00 AM' },
    { method: '💵 Cash App', from: 'Olivia → Pete', fee: '$0.73', time: '8:30 AM' },
  ];
  txns.forEach(tx => {
    y += 10;
    roundRect(ctx, 30, y, W - 60, 85, 12);
    ctx.fillStyle = CARD_BG; ctx.fill();
    ctx.strokeStyle = BORDER; ctx.lineWidth = 1; ctx.stroke();

    ctx.font = '26px sans-serif'; ctx.fillStyle = FG;
    ctx.fillText(tx.method, 55, y + 36);
    ctx.fillStyle = DIM; ctx.font = '22px sans-serif';
    ctx.fillText(tx.from, 55, y + 68);

    ctx.textAlign = 'right';
    ctx.fillStyle = ACCENT; ctx.font = 'bold 28px sans-serif';
    ctx.fillText(tx.fee, W - 55, y + 38);
    ctx.fillStyle = DIM; ctx.font = '20px sans-serif';
    ctx.fillText(tx.time, W - 55, y + 68);
    ctx.textAlign = 'left';
    y += 85;
  });

  save(c, 's6_income_1080x1920.png');
}

(async () => {
  genHomeScreen();
  genChatScreen();
  genPayScreen();
  await genScanToDownload();
  genSettingsScreen();
  genIncomeScreen();
  console.log('\nAll 6 screenshots generated!');
})();
