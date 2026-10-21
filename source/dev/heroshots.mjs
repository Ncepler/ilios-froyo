// Frames of the hero at given pour times (seconds), headless.  node source/dev/heroshots.mjs <outprefix> t0,t1,... [w h]
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
const [out, ts, w = 900, h = 600] = process.argv.slice(2);
const base = process.env.SITE || 'http://localhost:8080';
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const pg = await b.newPage({ viewport: { width: +w, height: +h } });
pg.on('pageerror', e => console.log('[pageerror]', e.message));
await pg.goto(base + '/index.html');
await pg.waitForFunction(() => window.__ilios && window.__ilios.setP, null, { timeout: 120000 });
await pg.addStyleTag({ content: '.nav,.band,.hint,#hint{display:none!important}' });
const info = await pg.evaluate(() => window.__ilios.pourInfo && window.__ilios.pourInfo());
console.log(JSON.stringify(info));
let i = 0;
for (const T of ts.split(',').map(Number)) {
  await pg.evaluate(T => { const I = window.__ilios; I.setP(I.pOfT(T)); }, T);
  await pg.waitForTimeout(250);
  await pg.screenshot({ path: `${out}-${String(i++).padStart(2, '0')}.png` });
}
await b.close();
