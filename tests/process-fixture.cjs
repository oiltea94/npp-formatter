const fs = require('node:fs');
const request = JSON.parse(fs.readFileSync(0, 'utf8'));
if (request.mode === 'arguments') {
  process.stdout.write(JSON.stringify({ args: process.argv.slice(2), cwd: process.cwd(), text: request.text }));
} else if (request.mode === 'hang') {
  setInterval(() => {}, 1000);
} else if (request.mode === 'stderr') {
  process.stderr.write('e'.repeat(256 * 1024));
  process.stdout.write(request.text);
} else if (request.mode === 'descendant') {
  require('node:child_process').spawn(process.execPath, ['-e', 'setInterval(() => {}, 1000)'], { stdio: 'inherit' });
  process.stdout.write('parent-exited');
  process.exit(0);
} else {
  process.stdout.write(request.text);
}
