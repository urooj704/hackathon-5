/**
 * Copies the Next.js app from frontend/web-form into the repository root
 * so Vercel can build when Root Directory is "." (repo root).
 * Source of truth remains frontend/web-form — run before `next build` / `next dev` from root.
 */

const fs = require('fs');
const path = require('path');

const repoRoot = path.join(__dirname, '..');
const src = path.join(repoRoot, 'frontend', 'web-form');

function rmrf(p) {
  if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
}

function cpDir(name) {
  const from = path.join(src, name);
  const to = path.join(repoRoot, name);
  if (!fs.existsSync(from)) return;
  rmrf(to);
  fs.cpSync(from, to, { recursive: true });
}

['pages', 'components', 'styles', 'lib', 'public'].forEach(cpDir);

for (const f of ['SupportForm.jsx', 'postcss.config.js', 'tailwind.config.js']) {
  const from = path.join(src, f);
  if (!fs.existsSync(from)) continue;
  fs.copyFileSync(from, path.join(repoRoot, f));
}

console.log('sync-frontend-to-root: mirrored frontend/web-form → repo root for Next build');
