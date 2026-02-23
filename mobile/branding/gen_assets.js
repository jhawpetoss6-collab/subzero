const path = require('path');
const fs = require('fs');
// Jimp is ESM in recent versions — load via dynamic import
let JimpLib = null;
async function getJimp(){
  if(!JimpLib){
    const mod = await import('jimp');
    JimpLib = mod.Jimp || mod.default || mod;
  }
  return JimpLib;
}

const root = path.resolve(__dirname, '..');
const logoPath = path.resolve(__dirname, 'logo.png');
const outIcon512 = path.resolve(root, 'icon-512.png');
const outIcon192 = path.resolve(root, 'icon-192.png');
const outIconMaskable = path.resolve(root, 'icon-512-maskable.png');
const outFeature = path.resolve(root, 'store', 'feature-graphic-1024x500.png');

function ensureDir(p) { fs.mkdirSync(p, { recursive: true }); }

function colorHex(hex){ if(typeof hex!== 'string') return 0x000000FF; const h=hex.replace('#',''); const n=parseInt(h,16); return (n<<8)|0xFF; }
async function makeIcon(size, outPath, bg = '#000000') {
  const Jimp = await getJimp();
  const img = await Jimp.read(logoPath);
  const canvas = await new Jimp({ width: size, height: size, color: colorHex(bg) });
  const max = Math.floor(size * 0.82);
  const scale = Math.min(max / img.bitmap.width, max / img.bitmap.height);
  img.scale(scale, Jimp.RESIZE_BILINEAR);
  const x = Math.floor((size - img.bitmap.width) / 2);
  const y = Math.floor((size - img.bitmap.height) / 2);
  canvas.composite(img, x, y, { mode: Jimp.BLEND_SOURCE_OVER, opacitySource: 1 });
  await canvas.write(outPath);
  console.log('Wrote', outPath);
}

async function makeMaskable(size, outPath) {
  // Same as icon but with larger safe zone (70%)
  const Jimp = await getJimp();
  const img = await Jimp.read(logoPath);
  const canvas = await new Jimp({ width: size, height: size, color: colorHex('#000000') });
  const max = Math.floor(size * 0.70);
  const scale = Math.min(max / img.bitmap.width, max / img.bitmap.height);
  img.scale(scale, Jimp.RESIZE_BILINEAR);
  const x = Math.floor((size - img.bitmap.width) / 2);
  const y = Math.floor((size - img.bitmap.height) / 2);
  canvas.composite(img, x, y);
  await canvas.write(outPath);
  console.log('Wrote', outPath);
}

async function makeFeature() {
  const W = 1024, H = 500;
  ensureDir(path.dirname(outFeature));
  const Jimp = await getJimp();
  const img = await Jimp.read(logoPath);
  const bg = await new Jimp({ width: W, height: H, color: colorHex('#000000') });
  // Scale logo to 70% of height
  const maxH = Math.floor(H * 0.72);
  const scale = maxH / img.bitmap.height;
  img.scale(scale, Jimp.RESIZE_BILINEAR);
  const x = Math.floor((W - img.bitmap.width) / 2);
  const y = Math.floor((H - img.bitmap.height) / 2);
  bg.composite(img, x, y);
  await bg.write(outFeature);
  console.log('Wrote', outFeature);
}

(async () => {
  if (!fs.existsSync(logoPath)) {
    console.error('Missing', logoPath);
    process.exit(1);
  }
  await makeIcon(512, outIcon512);
  await makeIcon(192, outIcon192);
  await makeMaskable(512, outIconMaskable);
  await makeFeature();
})();
