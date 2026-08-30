import { spawn, spawnSync } from 'node:child_process';
import crypto from 'node:crypto';
import {
  existsSync,
  mkdirSync,
  rmSync,
  writeFileSync,
} from 'node:fs';
import path from 'node:path';

const root = process.cwd();

const distDirectory = path.join(root, 'dist');
const runtimeDirectory = path.join(root, '.e2e-runtime');
const paymentDataDirectory = path.join(runtimeDirectory, 'payment-state');
const databasePath = path.join(runtimeDirectory, 'styledash.db');
const launcherPidPath = path.join(runtimeDirectory, 'server-launcher.pid');

if (!existsSync(path.join(distDirectory, 'index.html'))) {
  console.error(
    'E2E production build is missing. Run npm run build:e2e before starting the server.',
  );
  process.exit(1);
}

rmSync(runtimeDirectory, { recursive: true, force: true });
mkdirSync(paymentDataDirectory, { recursive: true });
writeFileSync(launcherPidPath, String(process.pid), { mode: 0o600 });

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
  STYLEDASH_PUBLIC_ORIGIN: 'http://127.0.0.1:4173',
  STYLEDASH_TRUST_LOOPBACK_PROXY: '1',

  // Enable the feature so authorization—not merely the flag—is exercised.
  STYLEDASH_ENABLE_TEST_PRODUCT: 'true',
  STYLEDASH_TEST_PRODUCT_ALLOWED_EMAILS: 'e2e-owner@example.test',

  PYTHONUTF8: '1',
});

// A Windows venv launcher can outlive a force-stopped Node wrapper. Keep the
// real Python server tied to this launcher's lifetime as a final safety net.
//
// NOTE: on Windows, os.kill(pid, 0) does not check liveness like POSIX signal
// 0 — it maps to CTRL_C_EVENT and calls GenerateConsoleCtrlEvent, which sends
// a real Ctrl+C to this process's own console on every poll. That previously
// crashed the server moments after startup. Use OpenProcess/GetExitCodeProcess
// on Windows instead, and keep the POSIX no-op signal check elsewhere.
const parentWatchRunner = `
import os, runpy, sys, threading, time

parent_pid = int(sys.argv[1])
server_path = sys.argv[2]
sys.argv = sys.argv[2:]

if sys.platform == 'win32':
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    def parent_alive():
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, parent_pid
        )
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
else:
    def parent_alive():
        try:
            os.kill(parent_pid, 0)
            return True
        except OSError:
            return False

def stop_with_parent():
    while True:
        time.sleep(0.25)
        if not parent_alive():
            os._exit(0)

threading.Thread(target=stop_with_parent, daemon=True).start()
runpy.run_path(server_path, run_name='__main__')
`;

const child = spawn(
  python,
  [
    '-c',
    parentWatchRunner,
    String(process.pid),
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

let stopping = false;

const stop = () => {
  if (
    stopping ||
    child.exitCode !== null ||
    child.signalCode !== null
  ) {
    return;
  }
  stopping = true;

  if (process.platform === 'win32' && child.pid) {
    const result = spawnSync(
      path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'taskkill.exe'),
      ['/pid', String(child.pid), '/T', '/F'],
      {
        stdio: 'ignore',
        windowsHide: true,
      },
    );
    if (result.status === 0) {
      return;
    }
  }

  child.kill('SIGTERM');
};

process.on('SIGINT', stop);
process.on('SIGTERM', stop);

child.on('error', error => {
  rmSync(launcherPidPath, { force: true });
  console.error('Could not start StyleDash E2E server:', error);
  process.exit(1);
});

child.on('exit', code => {
  rmSync(launcherPidPath, { force: true });
  process.exit(code ?? 0);
});
