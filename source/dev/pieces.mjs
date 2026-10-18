// Render the pieces lab (site/_pieces.html) headless and save a PNG. Needs the site served (cd site && python3 -m http.server 8080)
// and playwright (/opt/node-tools/node_modules).
//
//   node source/dev/pieces.mjs <out.png> "<query>" [auto[:elev:az:fov] | "cx,cy,cz|tx,ty,tz|fov"] [w h]
//
// query (URL params of _pieces.html): src=assets/models/<file>.glb  keys=strawberry,mango  scale=3 (x life size)  wrap=0.3 (row width, m)
// examples:
//   node source/dev/pieces.mjs /tmp/a.png "src=assets/models/_dev-x.glb&keys=mango&scale=4" auto 1400 700
//   node source/dev/pieces.mjs /tmp/a.png "src=assets/models/_dev-x.glb&scale=1" "0,0.17,0.30|0,0,0|30"      (the bar's distance)
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
import fs from 'node:fs';
const [out, query, cam = 'auto', w = 1400, h = 700] = process.argv.slice(2);
const base = process.env.SITE || 'http://localhost:8080';
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const pg = await b.newPage({ viewport: { width: +w, height: +h } });
pg.on('console', m => { if (['error', 'warning'].includes(m.type())) console.log('[console]', m.text().slice(0, 500)); });
pg.on('pageerror', e => console.log('[pageerror]', e.message));
await pg.goto(base + '/_pieces.html?' + query);
await pg.waitForFunction(() => window.labReady, null, { timeout: 120000 });
const data = await pg.evaluate(cam => {
  const L = window.lab;
  if (cam.startsWith('auto')) { const [, e, a, f] = cam.split(':'); L.auto(e ? +e : undefined, a ? +a : undefined, f ? +f : undefined); }
  else { const [c, t, fov] = cam.split('|'); L.view(c.split(',').map(Number), t.split(',').map(Number), +(fov || 30)); }
  return document.getElementById('c').toDataURL('image/png');
}, cam);
fs.writeFileSync(out, Buffer.from(data.split(',')[1], 'base64'));
console.log('ok:', await pg.evaluate(() => Object.entries(window.lab.P).map(([k, v]) => k + ' x' + v.length).join(', ')));
await b.close();
