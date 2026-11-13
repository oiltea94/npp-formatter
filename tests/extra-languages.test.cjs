const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { spawnSync } = require('node:child_process');
const bridge = path.resolve(__dirname, '../bridge/bridge.cjs');
const prettierPath = path.dirname(require.resolve('prettier/package.json'));
const cases = [
  { parser: 'php', extension: 'php', name: '@prettier/plugin-php', code: 'MISSING_PHP_PLUGIN',
    text: '<?php $answer=1+2;', expected: '<?php $answer = 1 + 2;\n' },
  { parser: 'sql', extension: 'sql', name: 'prettier-plugin-sql', code: 'MISSING_SQL_PLUGIN',
    text: 'select a,b from users where id=1;', expected: 'select\n  a,\n  b\nfrom\n  users\nwhere\n  id = 1;\n' },
  { parser: 'dot-properties', extension: 'properties', name: 'prettier-plugin-properties', code: 'MISSING_PROPERTIES_PLUGIN',
    text: 'greeting=hello\nanswer:42', expected: 'greeting = hello\nanswer = 42\n' },
  { parser: 'toml', extension: 'toml', name: 'prettier-plugin-toml', code: 'MISSING_TOML_PLUGIN',
    text: 'answer=42', expected: 'answer = 42\n' },
  { parser: 'sh', extension: 'sh', name: 'prettier-plugin-sh', code: 'MISSING_SH_PLUGIN',
    text: 'if true;then echo "hello";fi', expected: 'if true; then echo "hello"; fi\n' },
];
function project(t) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'npp-extra-'));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  return dir;
}
function invoke(overrides) {
  const child = spawnSync(process.execPath, [bridge], {
    input: JSON.stringify({ prettierPath, cursorOffset: 0, ...overrides }),
    encoding: 'utf8', timeout: 10000,
  });
  assert.ifError(child.error);
  return { ...JSON.parse(child.stdout), exitCode: child.status };
}
for (const item of cases) {
  test(`${item.parser}: discovers saved and untitled files; preserves cursor and idempotence`, t => {
    const dir = project(t);
    for (const request of [{ parser: item.parser }, { filePath: path.join(dir, `example.${item.extension.toUpperCase()}`) }]) {
      const result = invoke({ text: item.text, ...request });
      assert.equal(result.ok, true, result.error);
      assert.equal(result.formatted, item.expected);
      assert.equal(result.cursorOffset, 0);
      assert.equal(invoke({ text: result.formatted, ...request }).formatted, result.formatted);
    }
  });
  test(`${item.parser}: honors configured package and reports broken project copy`, t => {
    const dir = project(t);
    const filePath = path.join(dir, `example.${item.extension}`);
    fs.writeFileSync(path.join(dir, '.prettierrc.json'), JSON.stringify({ plugins: [item.name] }));
    assert.equal(invoke({ text: item.text, filePath }).formatted, item.expected);
    const pkg = path.join(dir, 'node_modules', item.name);
    fs.mkdirSync(pkg, { recursive: true });
    fs.writeFileSync(path.join(pkg, 'package.json'), '{"main":"index.cjs"}');
    fs.writeFileSync(path.join(pkg, 'index.cjs'), 'throw new Error("Broken project plugin");');
    const broken = invoke({ text: item.text, filePath });
    assert.match(broken.error, /Broken project plugin/);
    assert.notEqual(broken.code, item.code);
    assert.notEqual(broken.canChooseParser, true);
  });
}
test('optional language dependencies remain optional for built-ins and ignored files', t => {
  const dir = project(t);
  const standalone = path.join(dir, 'node_modules/prettier');
  fs.cpSync(prettierPath, standalone, { recursive: true });
  for (const item of cases) {
    const filePath = path.join(dir, `example.${item.extension}`);
    for (const request of [{ filePath }, { parser: item.parser }]) {
      const missing = invoke({ text: item.text, prettierPath: standalone, ...request });
      assert.equal(missing.code, item.code, missing.error);
      assert.equal(missing.formatted, undefined);
      assert.equal(missing.exitCode, 1);
      assert.notEqual(missing.canChooseParser, true);
    }
    assert.equal(invoke({ prettierPath: standalone, filePath, parser: 'json', text: '{"a":1}' }).formatted, '{ "a": 1 }\n');
    fs.writeFileSync(path.join(dir, '.prettierignore'), `*.${item.extension}\n`);
    assert.equal(invoke({ prettierPath: standalone, filePath, text: item.text }).ignored, true);
  }
});
test('SQL dialect is a default; project language and alternate formatter take precedence', t => {
  const dir = project(t);
  const filePath = path.join(dir, 'query.sql');
  const text = 'select [name] from [users];';
  const result = invoke({ text, filePath, sqlDialect: 'transactsql' });
  assert.equal(result.ok, true, result.error);
  assert.equal(result.formatted, 'select\n  [name]\nfrom\n  [users];\n');
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"language":"transactsql","keywordCase":"upper"}');
  assert.equal(invoke({ text, filePath, sqlDialect: 'mysql' }).formatted, 'SELECT\n  [name]\nFROM\n  [users];\n');
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"formatter":"node-sql-parser","database":"mysql"}');
  const alternate = invoke({ text: 'select a from users;', filePath, sqlDialect: 'transactsql' });
  assert.equal(alternate.ok, true, alternate.error);
  assert.match(alternate.formatted, /SELECT/);
});
test('every SQL dialect offered by the native settings is accepted by the pinned plugin', () => {
  const header = fs.readFileSync(path.resolve(__dirname, '../src/parser_selection.hpp'), 'utf8');
  const choices = [...header.matchAll(/\{L"[^"]+", L"([^"]+)"\}/g)].map(match => match[1]);
  assert.ok(choices.length >= 8);
  const supported = require('prettier-plugin-sql').options.language.choices.map(choice => choice.value);
  for (const choice of choices) assert.ok(supported.includes(choice), choice);
});
test('SQL and PHP syntax failures offer explicit language recovery without replacing text', () => {
  for (const [parser, text] of [['php', '<?php function {'], ['sql', 'select "']]) {
    const result = invoke({ parser, text });
    assert.equal(result.ok, false);
    assert.equal(result.formatted, undefined);
    assert.equal(result.canChooseParser, true, result.error);
  }
  const badOption = invoke({ parser: 'sql', text: 'select 1', sqlDialect: 'invalid-dialect' });
  assert.equal(badOption.ok, false);
  assert.notEqual(badOption.canChooseParser, true);
});
test('Properties preserves comments, duplicate keys, escapes, Unicode and project options', t => {
  const dir = project(t);
  const filePath = path.join(dir, 'messages.properties');
  const text = '# comment\ngreeting= 中文😀\nkey=one\nkey=two\npath=C:\\\\temp';
  const result = invoke({ text, filePath, cursorOffset: text.indexOf('中文'), endOfLine: 'crlf' });
  assert.equal(result.ok, true, result.error);
  assert.equal(result.formatted, '# comment\r\ngreeting = 中文😀\r\nkey = one\r\nkey = two\r\npath = C:\\\\temp\r\n');
  assert.equal(result.formatted.slice(result.cursorOffset, result.cursorOffset + 2), '中文');
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"keySeparator":": ","escapeNonLatin1":true}');
  const configured = invoke({ text: 'greeting=中文', filePath });
  assert.equal(configured.formatted, 'greeting: \\u4e2d\\u6587\n');
});

test('TOML preserves data, comments and project options, and rejects malformed input', t => {
  const dir = project(t);
  const filePath = path.join(dir, 'pyproject.toml');
  const text = '# comment\n[project]\nname="中文"\nvalues=[1,2,3]\n';
  const result = invoke({ text, filePath, endOfLine: 'crlf' });
  assert.equal(result.ok, true, result.error);
  assert.equal(result.formatted, '# comment\r\n[project]\nname = "中文"\nvalues = [1, 2, 3]\n'.replace(/(?<!\r)\n/g, '\r\n'));
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"singleQuote":true}');
  assert.match(invoke({ text, filePath }).formatted, /name = '中文'/);
  const invalid = invoke({ text: 'answer=[', parser: 'toml' });
  assert.equal(invalid.ok, false);
  assert.equal(invalid.canChooseParser, true, invalid.error);
  assert.equal(invalid.formatted, undefined);
});

test('Shell respects dialect and project precedence, preserves quoted heredoc and never executes input', t => {
  const dir = project(t);
  const filePath = path.join(dir, 'script.bash');
  const marker = path.join(dir, 'must-not-exist');
  const source = `# comment\ncat <<'EOF'\n  $HOME 中文\nEOF\nprintf '%s' "quoted value"\ntouch '${marker.replace(/\\/g, '/')}'\n`;
  const formatted = invoke({ text: source, filePath });
  assert.equal(formatted.ok, true, formatted.error);
  assert.match(formatted.formatted, /  \$HOME 中文\nEOF/);
  assert.match(formatted.formatted, /# comment/);
  assert.equal(fs.existsSync(marker), false);
  const text = 'values=(one two)';
  const invalid = invoke({ text, filePath, shellDialect: 2 });
  assert.equal(invalid.ok, false);
  assert.equal(invalid.formatted, undefined);
  assert.equal(invalid.canChooseParser, true, invalid.error);
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"variant":1}');
  assert.equal(invoke({ text, filePath, shellDialect: 2 }).formatted, 'values=(one two)\n');
});

test('every offered Shell dialect is accepted and invalid options stay distinct from syntax errors', async () => {
  const { options } = await import('prettier-plugin-sh');
  for (const shellDialect of [1, 2, 4, 8]) {
    assert.ok(options.variant.choices.some(choice => choice.value === shellDialect));
    const result = invoke({ parser: 'sh', shellDialect, text: 'echo hello' });
    assert.equal(result.ok, true, result.error);
  }
  const invalid = invoke({ parser: 'sh', shellDialect: 999, text: 'echo hello' });
  assert.equal(invalid.ok, false);
  assert.notEqual(invalid.canChooseParser, true);
});

test('Shell cursor mapping handles nested AST objects, Unicode and CRLF', () => {
  const text = '# 中文😀\r\nif true;then\r\necho "value"\r\nfi';
  for (const token of ['中文', 'value', 'fi']) {
    const result = invoke({ text, parser: 'sh', cursorOffset: text.indexOf(token), endOfLine: 'crlf' });
    assert.equal(result.ok, true, result.error);
    assert.equal(result.formatted.slice(result.cursorOffset, result.cursorOffset + token.length), token);
    assert.equal(/(?<!\r)\n/.test(result.formatted), false);
  }
});

test('older Prettier remains usable for built-ins and reports the Shell version requirement', t => {
  const dir = project(t);
  fs.writeFileSync(path.join(dir, 'package.json'), '{"name":"prettier","version":"3.5.0","main":"index.cjs"}');
  fs.writeFileSync(path.join(dir, 'index.cjs'), `module.exports={...require(${JSON.stringify(prettierPath)}),version:'3.5.0'};`);
  const shell = invoke({ prettierPath: dir, parser: 'sh', text: 'echo hello' });
  assert.equal(shell.ok, false);
  assert.match(shell.error, /Prettier 3\.6 or later/);
  assert.notEqual(shell.canChooseParser, true);
  const core = invoke({ prettierPath: dir, parser: 'json', text: '{"a":1}' });
  assert.equal(core.formatted, '{ "a": 1 }\n');
  const report = invoke({ operation: 'checkEnvironment', prettierPath: dir });
  assert.equal(report.prettier.version, '3.5.0');
  const item = report.plugins.find(item => item.parser === 'sh');
  assert.equal(item.status, 'error');
  assert.match(item.error, /Prettier 3\.6 or later/);
});

test('TOML reports its Node version requirement before loading native code', () => {
  const child = spawnSync(process.execPath, ['-e',
    `Object.defineProperty(process.versions,'node',{value:'18.20.8'});require(${JSON.stringify(bridge)});`], {
    input: JSON.stringify({ prettierPath, cursorOffset: 0, text: 'answer=42', parser: 'toml' }),
    encoding: 'utf8', timeout: 10000,
  });
  assert.ifError(child.error);
  assert.equal(child.status, 1);
  const result = JSON.parse(child.stdout);
  assert.match(result.error, /Node.js 20 or later/);
  assert.equal(result.formatted, undefined);
  assert.notEqual(result.canChooseParser, true);
});
