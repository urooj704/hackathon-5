/**
 * When Vercel Root Directory is `frontend`, it expects `.next` here.
 * The real Next app lives in `frontend/web-form`; copy its build output up one level.
 */

const fs = require('fs');
const path = require('path');

const frontendRoot = __dirname;
const from = path.join(frontendRoot, 'web-form', '.next');
const to = path.join(frontendRoot, '.next');

if (!fs.existsSync(from)) {
  console.error('sync-next-output: missing', from);
  process.exit(1);
}

fs.rmSync(to, { recursive: true, force: true });
fs.cpSync(from, to, { recursive: true });
console.log('sync-next-output: copied web-form/.next → frontend/.next');
