// Photograph bowls of the live bar, headless, from the angle you meet them at (and a closer, higher one).
//   node source/dev/bowls.mjs <outdir> key1,key2,... [w h] [dist]
// Needs the site served (cd site && python3 -m http.server 8080) and playwright (/opt/node-tools/node_modules).
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
const [outdir, keys, w = 900, h = 560, dist = 0.3] = process.argv.slice(2);
const base = process.env.SITE || 'http://localhost:8080';
const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const pg = await b.newPage({ viewport: { width: +w, height: +h } });
pg.on('console', m => { if (['error'].includes(m.type())) console.log('[console]', m.text().slice(0, 300)); });
pg.on('pageerror', e => console.log('[pageerror]', e.message));
await pg.goto(base + '/index.html');
await pg.evaluate(() => window.__startToppings && window.__startToppings());
await pg.waitForFunction(() => window.__bar, null, { timeout: 240000 });
await pg.addStyleTag({ content: '.nav,#barintro,#barline,#barend,#bartip{display:none!important}' });
await pg.evaluate(() => { document.querySelector('#bar').scrollIntoView(); });
await pg.waitForTimeout(500);
const list = keys === 'all' ? await pg.evaluate(() => window.__bar.items.map(i => i.def.key)) : keys.split(',');
for (const k of list) {
  await pg.evaluate(([k, d]) => {
    const bar = window.__bar, it = bar.items.find(i => i.def.key === k);
    bar.pause(true);
    const p = bar.xOf(k); bar.jump(p);
    const x = it.x, z = it.z;
    bar.debugCam([x, 0.17 + d * 0.15, z + d], [x, 0.045, z]);
    bar.render();
  }, [k, +dist]);
  await pg.waitForTimeout(300);
  await pg.locator('#barcanvas').screenshot({ path: `${outdir}/${k}.png` });
  console.log('shot', k);
}
await b.close();
