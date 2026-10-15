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
h = h.replace('<script type="module" src="main.js"></script>', '<script type="module">\n' + js + "\n</script>")
open(out, "w", encoding="utf8").write(h)
print("wrote", out, len(h))
