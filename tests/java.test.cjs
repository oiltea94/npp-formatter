const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');

const bridge = path.resolve(__dirname, '../bridge/bridge.cjs');
const prettierPath = path.dirname(require.resolve('prettier/package.json'));
const javaEntry = require.resolve('prettier-plugin-java');
const source = 'class Hello{void run(){String s="中文😀";System.out.println(s);}}';

function project(t, prefix = 'npp java 中文 ') {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}

function invoke(overrides) {
  const child = spawnSync(process.execPath, [bridge], {
    input: JSON.stringify({ prettierPath, text: source, cursorOffset: 0, ...overrides }),
    encoding: 'utf8', timeout: 10000,
  });
  assert.ifError(child.error);
  const result = JSON.parse(child.stdout);
  return { ...result, exitCode: child.status };
}

function brokenProjectPlugin(dir) {
  const pkg = path.join(dir, 'node_modules/prettier-plugin-java');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(path.join(pkg, 'package.json'), '{"name":"prettier-plugin-java","main":"index.cjs"}');
  fs.writeFileSync(path.join(pkg, 'index.cjs'), 'throw new Error("Project Java plugin failed to load");');
}

test('formats saved Java without a Prettier config using the adjacent optional package', (t) => {
  const dir = project(t);
  for (const extension of ['java', 'JAVA']) {
    const result = invoke({ filePath: path.join(dir, `Hello.${extension}`) });
    assert.equal(result.ok, true, result.error);
    assert.match(result.formatted, /class Hello \{/);
  }
});

test('formats untitled Java and preserves a Unicode cursor and idempotence', () => {
  const result = invoke({ parser: 'java', cursorOffset: source.indexOf('System') });
  assert.equal(result.ok, true, result.error);
  assert.equal(result.formatted.slice(result.cursorOffset, result.cursorOffset + 6), 'System');
  const repeated = invoke({ parser: 'java', text: result.formatted, cursorOffset: result.cursorOffset });
  assert.equal(repeated.formatted, result.formatted);
  assert.equal(repeated.cursorOffset, result.cursorOffset);
});

test('keeps Java project options and respects explicit parser precedence', (t) => {
  const dir = project(t);
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"tabWidth":4}');
  const filePath = path.join(dir, 'Hello.java');
  const result = invoke({ filePath });
  assert.equal(result.ok, true, result.error);
  assert.match(result.formatted, /\n    void run\(\)/);
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"parser":"babel","semi":false}');
  const js = invoke({ filePath, text: 'const a=1;' });
  assert.equal(js.formatted, 'const a = 1\n');
  const overridden = invoke({ filePath, parser: 'java' });
  assert.equal(overridden.ok, true, overridden.error);
});

test('prefers a project Java dependency and reports its load error without falling back', (t) => {
  const dir = project(t);
  brokenProjectPlugin(dir);
  const result = invoke({ filePath: path.join(dir, 'Hello.java') });
  assert.equal(result.ok, false);
  assert.match(result.error, /Project Java plugin failed to load/);
  assert.notEqual(result.code, 'MISSING_JAVA_PLUGIN');
  assert.notEqual(result.canChooseParser, true);
});

test('honors an explicitly configured Java plugin object before auto discovery', (t) => {
  const dir = project(t);
  brokenProjectPlugin(dir);
  fs.writeFileSync(path.join(dir, '.prettierrc.cjs'),
    `module.exports = { plugins: [require(${JSON.stringify(javaEntry)})] };`);
  const result = invoke({ filePath: path.join(dir, 'Hello.java') });
  assert.equal(result.ok, true, result.error);
});

test('loads a configured Java package name from the selected Prettier installation', (t) => {
  const dir = project(t);
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"plugins":["prettier-plugin-java"]}');
  const result = invoke({ filePath: path.join(dir, 'Hello.java') });
  assert.equal(result.ok, true, result.error);
});

test('reports a broken project package entry instead of using another installation', (t) => {
  const dir = project(t);
  const pkg = path.join(dir, 'node_modules/prettier-plugin-java');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(path.join(pkg, 'package.json'), '{"name":"prettier-plugin-java","main":"missing.cjs"}');
  const result = invoke({ filePath: path.join(dir, 'Hello.java') });
  assert.equal(result.ok, false);
  assert.match(result.error, /missing\.cjs/);
  assert.notEqual(result.code, 'MISSING_JAVA_PLUGIN');
  assert.notEqual(result.canChooseParser, true);
});

test('recognizes Java syntax errors for explicit language recovery', () => {
  const result = invoke({ parser: 'java', text: 'class Broken { void run( {' });
  assert.equal(result.ok, false);
  assert.equal(result.exitCode, 1);
  assert.equal(result.formatted, undefined);
  assert.match(result.error, /Failed to parse/);
  assert.equal(result.canChooseParser, true);
});

test('reports missing Java with a stable code while built-ins and ignored files still work', (t) => {
  const dir = project(t);
  const standalone = path.join(project(t, 'npp-java-runtime-'), 'node_modules/prettier');
  fs.cpSync(prettierPath, standalone, { recursive: true });
  assert.equal(JSON.parse(fs.readFileSync(path.join(standalone, 'package.json'), 'utf8')).name, 'prettier');
  const request = { prettierPath: standalone, filePath: path.join(dir, 'Hello.java') };
  for (const override of [{}, { filePath: undefined, parser: 'java' }]) {
    const missing = invoke({ ...request, ...override });
    assert.equal(missing.code, 'MISSING_JAVA_PLUGIN', missing.error);
    assert.equal(missing.ok, false);
    assert.equal(missing.exitCode, 1);
    assert.equal(missing.formatted, undefined);
    assert.notEqual(missing.canChooseParser, true);
  }
  const js = invoke({ ...request, parser: 'babel', text: 'const a=1;' });
  assert.equal(js.formatted, 'const a = 1;\n');
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"plugins":["prettier-plugin-java"]}');
  assert.equal(invoke(request).code, 'MISSING_JAVA_PLUGIN');
  fs.writeFileSync(path.join(dir, '.prettierignore'), '*.java\n');
  const ignored = invoke(request);
  assert.equal(ignored.ok, true, ignored.error);
  assert.equal(ignored.ignored, true);
});
