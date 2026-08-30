import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';

const root = process.cwd();
const npmTask = args => process.platform === 'win32'
  ? [process.env.ComSpec || 'cmd.exe', ['/d', '/s', '/c', `npm ${args.join(' ')}`]]
  : ['npm', args];
const venvPython = process.platform === 'win32'
  ? path.join(root, '.venv', 'Scripts', 'python.exe')
  : path.join(root, '.venv', 'bin', 'python');
const python = process.env.STYLEDASH_VERIFY_PYTHON
  || (existsSync(venvPython) ? venvPython : process.platform === 'win32' ? 'python' : 'python3');

const tasks = [
  ['typecheck', ...npmTask(['run', 'typecheck'])],
  ['lint', ...npmTask(['run', 'lint'])],
  ['unit', ...npmTask(['test'])],
  ['backend', python, ['-m', 'unittest', 'discover', '-s', 'server/tests', '-p', 'test_*.py']],
];

const startedAt = Date.now();
const run = ([name, command, args]) => new Promise(resolve => {
  let child;
  try {
    child = spawn(command, args, { cwd: root, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (error) {
    console.error(`[${name}] could not start: ${error.message}`);
    resolve({ name, code: 1 });
    return;
  }
  const write = (stream, chunk) => {
    for (const line of String(chunk).split(/\r?\n/)) {
      if (line) stream.write(`[${name}] ${line}\n`);
    }
  };
  child.stdout.on('data', chunk => write(process.stdout, chunk));
  child.stderr.on('data', chunk => write(process.stderr, chunk));
  child.on('error', error => {
    console.error(`[${name}] could not start: ${error.message}`);
    resolve({ name, code: 1 });
  });
  child.on('exit', code => resolve({ name, code: code ?? 1 }));
});

const results = await Promise.all(tasks.map(run));
const elapsedSeconds = ((Date.now() - startedAt) / 1000).toFixed(1);
for (const result of results) console.log(`[verify] ${result.name}: ${result.code === 0 ? 'PASS' : 'FAIL'}`);
console.log(`[verify] parallel checks completed in ${elapsedSeconds}s`);
process.exitCode = results.some(result => result.code !== 0) ? 1 : 0;
