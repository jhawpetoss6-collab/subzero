const fs = require('fs');
const path = require('path');
let JimpLib=null;async function J(){ if(!JimpLib){ const m=await import('jimp'); JimpLib=m.Jimp||m.default||m; } return JimpLib; }

const inDir = process.env.IN_DIR || path.resolve(__dirname,'..','mobile','store','screens','inbox');
const outDir = process.env.OUT_DIR || path.resolve(__dirname,'..','mobile','store','screens','processed');
fs.mkdirSync(outDir,{recursive:true});

function listImages(dir){return fs.readdirSync(dir).filter(f=>/\.(png|jpg|jpeg)$/i.test(f)).map(f=>path.join(dir,f));}

async function fit1080x1920(src, dest){
  const Jimp = await J();
  const targetW=1080, targetH=1920;
  const img = await Jimp.read(src);
  // Scale to fit height
  const scale = targetH / img.bitmap.height;
  img.scale(scale);
  let canvas = await new Jimp({width:targetW, height:targetH, color:0x000000FF});
  if(img.bitmap.width > targetW){
    // center-crop width
    const x = Math.floor((img.bitmap.width - targetW)/2);
    const cropped = img.clone().crop(x,0,targetW,targetH);
    canvas.composite(cropped,0,0);
  } else {
    const x = Math.floor((targetW - img.bitmap.width)/2);
    canvas.composite(img,x,0);
  }
  await canvas.write(dest);
}

(async()=>{
  const files=listImages(inDir);
  if(!files.length){ console.error('No images found in', inDir); process.exit(1); }
  let n=1;
  for(const f of files){
    const out = path.join(outDir, `s${n++}_1080x1920.png`);
    await fit1080x1920(f,out);
    console.log('Wrote', out);
  }
})();
