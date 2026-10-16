"""Turn site/index.html + main.js into a single artifact page (scratch output, not committed).

- strips the document skeleton (the artifact host adds its own)
- three.js comes from jsdelivr (the artifact CSP allows scripts from there)
- main.js is inlined as a module script; models, json and images stay as published files
"""
import re
import sys

site, out = sys.argv[1], sys.argv[2]
h = open(f"{site}/index.html", encoding="utf8").read()
js = open(f"{site}/main.js", encoding="utf8").read()

h = re.sub(r"<!doctype html>\s*<html[^>]*>\s*<head>\s*", "", h, flags=re.I)
h = re.sub(r"</head>\s*<body>\s*", "", h, flags=re.I)
h = re.sub(r"</body>\s*</html>\s*$", "", h, flags=re.I)
h = re.sub(r'<meta charset="utf-8">\s*', "", h)
h = re.sub(r'<meta name="viewport"[^>]*>\s*', "", h)
h = h.replace('<link rel="modulepreload" href="vendor/three/three.module.min.js">\n', "")
h = h.replace('"three": "./vendor/three/three.module.min.js"',
              '"three": "https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.min.js"')
h = h.replace('"three/addons/": "./vendor/three/addons/"',
              '"three/addons/": "https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"')
# artifacts don't serve .glb: models ship as base64 text and are parsed in the page
js = js.replace(
    "const load = url => new Promise((res, rej) => loader.load(url, res, undefined, rej));",
    "const load = url => fetch(url + '.b64.txt').then(r => { if (!r.ok) throw new Error(r.status); return r.text(); })\n"
    "  .then(t => { const bin = atob(t.trim()); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);\n"
    "    manager.itemStart(url); return new Promise((res, rej) => loader.parse(u.buffer, '', g => { manager.itemEnd(url); res(g); }, rej)); });")
assert ".b64.txt" in js
# the pour's binary ships the same way
old_bin = "const loadBin = url => fetch(url).then(r => { if (!r.ok) throw new Error(url + ' ' + r.status); return r.arrayBuffer(); });"
assert old_bin in js
js = js.replace(old_bin,
    "const loadBin = url => fetch(url + '.b64.txt').then(r => { if (!r.ok) throw new Error(url + ' ' + r.status); return r.text(); })\n"
    "  .then(t => { const bin = atob(t.trim()); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u.buffer; });")
# froyo.js is inlined ahead of main.js (one module, one THREE import)
fj = open(f"{site}/froyo.js", encoding="utf8").read()
fj = fj.replace("import * as THREE from 'three';\n", "").replace("export class", "class")
assert "import { FroyoPour } from './froyo.js';" in js
js = js.replace("import { FroyoPour } from './froyo.js';", "")
js = js.replace("import * as THREE from 'three';", "import * as THREE from 'three';\n" + fj.split("\n// the 12 cube", 1)[0].split("import { edgeTable")[0] + "import { edgeTable, triTable } from 'three/addons/objects/MarchingCubes.js';\n", 1) if False else js
imports = [l for l in fj.splitlines() if l.startswith("import ")]
fj = "\n".join(l for l in fj.splitlines() if not l.startswith("import "))
js = js.replace("import * as THREE from 'three';", "import * as THREE from 'three';\n" + "\n".join(imports), 1)
js = js + "\n" + fj
h = h.replace('"fflate": "./vendor/fflate.js"', '"fflate": "https://cdn.jsdelivr.net/npm/fflate@0.8.2/esm/browser.js"')
h = h.replace('<script type="module" src="main.js"></script>', '<script type="module">\n' + js + "\n</script>")
open(out, "w", encoding="utf8").write(h)
print("wrote", out, len(h))
