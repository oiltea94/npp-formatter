const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const bridge = path.resolve(__dirname, '../bridge/bridge.cjs');
const prettierPath = path.dirname(require.resolve('prettier/package.json'));
function invoke(overrides = {}) {
  const result = spawnSync(process.execPath, [bridge], {
    input: JSON.stringify({ operation: 'checkEnvironment', prettierPath, ...overrides }),
    encoding: 'utf8', timeout: 30000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return JSON.parse(result.stdout);
}
function project(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'npp-environment-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}
test('environment reports actual runtime, Prettier and seven loaded language packages', () => {
  const report = invoke();
  assert.equal(report.node.version, process.versions.node);
  assert.equal(report.node.arch, process.arch);
  assert.equal(report.prettier.version, require('prettier/package.json').version);
  assert.equal(report.plugins.length, 7);
  for (const item of report.plugins) {
    assert.equal(item.status, 'available', JSON.stringify(item));
    assert.ok(item.version, JSON.stringify(item));
    assert.ok(path.isAbsolute(item.path));
  }
  assert.equal(report.formatted, undefined);
});
test('environment distinguishes missing optional dependencies from available core', t => {
  const dir = project(t);
  const standalone = path.join(dir, 'node_modules/prettier');
  fs.cpSync(prettierPath, standalone, { recursive: true });
  const report = invoke({ prettierPath: standalone });
  assert.equal(report.prettier.status, 'available');
  for (const item of report.plugins) assert.equal(item.status, 'missing', JSON.stringify(item));
  assert.equal(fs.existsSync(path.join(dir, 'package-lock.json')), false);
});
test('environment reports invalid Prettier and configuration without hiding Node version', t => {
  const dir = project(t);
  const report = invoke({ prettierPath: dir });
  assert.equal(report.node.version, process.versions.node);
  assert.equal(report.prettier.status, 'error');
  assert.match(report.prettier.error, /package.json/);
  assert.deepEqual(report.plugins, []);
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{broken');
  const invalid = invoke({ filePath: path.join(dir, 'file.toml') });
  assert.ok(invalid.configError);
  assert.deepEqual(invalid.plugins, []);
});
test('environment respects project precedence and probes lazily broken parsers', t => {
  const dir = project(t);
  const pkg = path.join(dir, 'node_modules/prettier-plugin-toml');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(path.join(pkg, 'package.json'), '{"main":"index.cjs","version":"9.8.7"}');
  fs.writeFileSync(path.join(pkg, 'index.cjs'), `module.exports={parsers:{toml:{astFormat:'toml',parse(){throw new Error('lazy native binding failed')},locStart:()=>0,locEnd:()=>0}},printers:{toml:{print:()=>''}}};`);
  const report = invoke({ filePath: path.join(dir, 'file.toml') });
  const toml = report.plugins.find(item => item.parser === 'toml');
  assert.equal(toml.version, '9.8.7');
  assert.equal(toml.status, 'error');
  assert.match(toml.error, /lazy native binding failed/);
  assert.equal(report.plugins.find(item => item.parser === 'java').status, 'available');
});
test('environment honors a configured custom plugin path', t => {
  const dir = project(t);
  fs.writeFileSync(path.join(dir, 'custom.cjs'), `module.exports={parsers:{toml:{astFormat:'toml',parse:x=>x,locStart:()=>-1,locEnd:()=>-1}},printers:{toml:{print:()=> 'custom = true\\n'}}};`);
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"plugins":["./custom.cjs"]}');
  const report = invoke({ filePath: path.join(dir, 'file.toml') });
  const toml = report.plugins.find(item => item.parser === 'toml');
  assert.equal(toml.status, 'available', toml.error);
  assert.equal(toml.path, path.join(dir, 'custom.cjs'));
});
