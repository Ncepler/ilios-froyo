// Frames of the pour from the froyo lab (site/_lab.html), for judging the end of the pour.
//   node source/dev/pourshots.mjs <outprefix> t0,t1,t2,... [cx,cy,cz|tx,ty,tz|fov] [w h]     (t < 0: the finished pour)
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const [out, ts, cam = '0.14,0.16,0.30|0,0.09,0|24', w = 700, h = 700] = process.argv.slice(2);
const base = process.env.SITE || 'http://localhost:8080';
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const pg = await b.newPage({ viewport: { width: +w, height: +h } });
pg.on('pageerror', e => console.log('[pageerror]', e.message));
await pg.goto(base + '/_lab.html' + (process.env.Q || ''));
await pg.waitForFunction(() => window.labReady, null, { timeout: 120000 });
console.log(await pg.evaluate(() => JSON.stringify({ dur: window.lab.rec.duration, release: window.lab.rec.releaseT, simMs: window.lab.simMs })));
const [c, t, fov] = cam.split('|');
let i = 0;
for (const T of ts.split(',').map(Number)) {
  const data = await pg.evaluate(([T, c, t, fov]) => { window.lab.set(T, c.split(',').map(Number), t.split(',').map(Number), +fov); return document.getElementById('c').toDataURL('image/png'); }, [T, c, t, fov]);
  fs.writeFileSync(`${out}-${String(i++).padStart(2, '0')}.png`, Buffer.from(data.split(',')[1], 'base64'));
}
await b.close();
