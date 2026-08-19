import {
  existsSync,
  readFileSync,
  rmSync,
} from 'node:fs';
import path from 'node:path';

const launcherPidPath = path.join(
  process.cwd(),
  '.e2e-runtime',
  'server-launcher.pid',
);

const delay = milliseconds =>
  new Promise(resolve => setTimeout(resolve, milliseconds));

const processExists = pid => {
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    if (error?.code === 'ESRCH') {
      return false;
    }
    throw error;
  }
};

export default async function globalTeardown() {
  if (!existsSync(launcherPidPath)) {
    return;
  }

  const pid = Number.parseInt(readFileSync(launcherPidPath, 'utf8').trim(), 10);
  if (!Number.isSafeInteger(pid) || pid <= 0) {
    throw new Error('StyleDash E2E server launcher PID is invalid.');
  }

  // Stop the known launcher before Playwright falls back to Windows taskkill,
  // which can be denied and otherwise leaves its inherited handles open.
  try {
    process.kill(pid, 'SIGTERM');
  } catch (error) {
    if (error?.code !== 'ESRCH') {
      throw error;
    }
  }

  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (!processExists(pid)) {
      rmSync(launcherPidPath, { force: true });
      return;
    }
    await delay(100);
  }

  throw new Error(`StyleDash E2E server launcher ${pid} did not stop.`);
}
