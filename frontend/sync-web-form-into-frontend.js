/**
 * Mirror canonical app from ./web-form into this directory (./).
 * Vercel Root Directory = "frontend" expects pages/, next.config, etc. here.
 * Source of truth stays in web-form/.
 */

const fs = require('fs');
const path = require('path');

const dest = __dirname;
const src = path.join(dest, 'web-form');

function rmrf(p) {
  if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
}

function cpDir(name) {
  const from = path.join(src, name);
  const to = path.join(dest, name);
  if (!fs.existsSync(from)) return;
  rmrf(to);
  fs.cpSync(from, to, { recursive: true });
}

['pages', 'components', 'styles', 'lib', 'public'].forEach(cpDir);

for (const f of ['SupportForm.jsx', 'postcss.config.js', 'tailwind.config.js']) {
  const from = path.join(src, f);
  if (!fs.existsSync(from)) continue;
  fs.copyFileSync(from, path.join(dest, f));
}

console.log('sync-web-form-into-frontend: mirrored web-form/ → frontend/');
