import { spawn } from 'node:child_process';
import crypto from 'node:crypto';
import {
  existsSync,
  mkdirSync,
  rmSync,
} from 'node:fs';
import path from 'node:path';

const root = process.cwd();

const distDirectory = path.join(root, 'dist');
const runtimeDirectory = path.join(root, '.e2e-runtime');
const paymentDataDirectory = path.join(runtimeDirectory, 'payment-state');
const databasePath = path.join(runtimeDirectory, 'styledash.db');

if (!existsSync(path.join(distDirectory, 'index.html'))) {
  console.error(
    'E2E production build is missing. Run npm run build:e2e before starting the server.',
  );
  process.exit(1);
}

rmSync(runtimeDirectory, { recursive: true, force: true });
mkdirSync(paymentDataDirectory, { recursive: true });

const windowsVenvCandidates = [
  path.resolve(root, '.venv', 'Scripts', 'python.exe'),
  path.resolve(root, '..', '..', '.venv', 'Scripts', 'python.exe'),
];

const windowsVenvPython = windowsVenvCandidates.find(candidate =>
  existsSync(candidate),
);

const python =
  process.env.STYLEDASH_E2E_PYTHON ||
  windowsVenvPython ||
  (process.platform === 'win32' ? 'python' : 'python3');

const fernetKey = crypto
  .randomBytes(32)
  .toString('base64')
  .replace(/\+/g, '-')
  .replace(/\//g, '_');

const env = { ...process.env };

// Never inherit real payment/mail/runtime configuration into E2E.
for (const name of Object.keys(env)) {
  if (
    name.startsWith('RAZORPAY_') ||
    name.startsWith('STYLEDASH_SMTP_') ||
    name.startsWith('STYLEDASH_PASSWORD_RESET_') ||
    [
      'STYLEDASH_TOTP_ENCRYPTION_KEY',
      'STYLEDASH_DATABASE_PATH',
      'STYLEDASH_DATA_DIR',
      'STYLEDASH_SUPPORTED_PINCODES',
      'STYLEDASH_ENABLE_TEST_PRODUCT',
      'STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS',
    ].includes(name)
  ) {
    delete env[name];
  }
}

Object.assign(env, {
  RAZORPAY_MODE: 'test',

  STYLEDASH_TOTP_ENCRYPTION_KEY: fernetKey,
  STYLEDASH_DATABASE_PATH: databasePath,
  STYLEDASH_DATA_DIR: paymentDataDirectory,

  STYLEDASH_SUPPORTED_PINCODES: '458441',

  // Enable the feature so authorization—not merely the flag—is exercised.
  STYLEDASH_ENABLE_TEST_PRODUCT: 'true',
  STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS: 'e2e-owner@example.test',

  PYTHONUTF8: '1',
});

const child = spawn(
  python,
  [
    path.join(root, 'scripts', 'termux-spa-server.py'),
    '--bind',
    '127.0.0.1',
    '--port',
    '4173',
    '--directory',
    distDirectory,
    '--catalog',
    path.join(root, 'server', 'payment-data', 'catalog.json'),
    '--settings',
    path.join(root, 'server', 'payment-data', 'settings.json'),
    '--data-directory',
    paymentDataDirectory,
  ],
  {
    cwd: root,
    env,
    stdio: 'inherit',
  },
);

const stop = () => {
  if (!child.killed) {
    child.kill();
  }
};

process.on('SIGINT', stop);
process.on('SIGTERM', stop);

child.on('error', error => {
  console.error('Could not start StyleDash E2E server:', error);
  process.exit(1);
});

child.on('exit', code => {
  process.exit(code ?? 0);
});
