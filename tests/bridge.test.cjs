const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const bridge = path.resolve(__dirname, '../bridge/bridge.cjs');
const prettierPath = path.dirname(require.resolve('prettier/package.json'));

function invoke(overrides, raw) {
  const request = { text: '{"中文":"😀","a":1}', parser: 'json',
    prettierPath, cursorOffset: 0, ...overrides };
  const child = spawnSync(process.execPath, [bridge], {
    input: raw ?? JSON.stringify(request), encoding: 'utf8', timeout: 10000,
  });
  assert.ifError(child.error);
  assert.ok(child.stdout, child.stderr);
  return { ...JSON.parse(child.stdout), exitCode: child.status };
}

test('formats an untitled JSON document including Chinese and emoji', () => {
  const result = invoke({});
  assert.equal(result.ok, true);
  assert.equal(result.formatted, '{ "中文": "😀", "a": 1 }\n');
  assert.equal(result.exitCode, 0);
});

test('keeps a UTF-16 cursor on its token after an emoji', () => {
  const text = 'const emoji="😀";const answer=42;';
  const result = invoke({ text, parser: 'babel', cursorOffset: text.indexOf('answer') });
  assert.equal(result.ok, true);
  assert.equal(result.formatted.slice(result.cursorOffset, result.cursorOffset + 6), 'answer');
});

test('loads project configuration and honors the nearest ignore file', (t) => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'npp formatter 中文 '));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  fs.writeFileSync(path.join(dir, '.prettierrc'), '{"singleQuote":true,"semi":false}');
  fs.writeFileSync(path.join(dir, '.prettierignore'), 'ignored.js\n');
  const result = invoke({ filePath: path.join(dir, 'input.js'),
    text: 'const s="hello";', parser: undefined });
  assert.equal(result.ok, true);
  assert.equal(result.formatted, "const s = 'hello'\n");
  const ignored = invoke({ filePath: path.join(dir, 'ignored.js'), parser: undefined });
  assert.equal(ignored.ok, true);
  assert.equal(ignored.ignored, true);
});

test('returns a structured syntax error without a replacement', () => {
  const result = invoke({ text: '{oops' });
  assert.equal(result.ok, false);
  assert.equal(result.formatted, undefined);
  assert.match(result.error, /SyntaxError|Expected|Unexpected/);
});

test('rejects invalid dependency paths rather than loading another installation', () => {
  const result = invoke({ prettierPath: path.join(os.tmpdir(), 'missing-npp-prettier-package') });
  assert.equal(result.ok, false);
  assert.match(result.error, /Prettier|prettier/);
});

test('requires a parser or saved file path', () => {
  const result = invoke({ parser: '' });
  assert.equal(result.ok, false);
  assert.match(result.error, /parser/i);
});

test('invalid JSON produces a machine-readable error', () => {
  const result = invoke({}, '{');
  assert.equal(result.ok, false);
  assert.equal(typeof result.error, 'string');
});

test('CRLF preference is preserved when configuration does not override it', () => {
  const result = invoke({ text: 'const x=1;\r\nconst y=2;\r\n', parser: 'babel', endOfLine: 'crlf' });
  assert.equal(result.formatted, 'const x = 1;\r\nconst y = 2;\r\n');
});
