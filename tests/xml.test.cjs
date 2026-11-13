const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { pathToFileURL } = require('node:url');
const { spawnSync } = require('node:child_process');

const bridge = path.resolve(__dirname, '../bridge/bridge.cjs');
const prettierPath = path.dirname(require.resolve('prettier/package.json'));
const xmlEntry = require.resolve('@prettier/plugin-xml');
const source = '<root><item name="中文😀"/></root>';
const expected = '<root><item name="中文😀" /></root>\n';

function project(t, prefix = 'npp xml 中文 ') {
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
  return { ...JSON.parse(child.stdout), exitCode: child.status };
}

test('discovers XML for saved XML, SVG, XSD, XSLT, XAML and resource files', (t) => {
  const dir = project(t);
  for (const extension of ['xml', 'XML', 'svg', 'xsd', 'xsl', 'xslt', 'xaml', 'resx']) {
    const result = invoke({ filePath: path.join(dir, `example.${extension}`) });
    assert.equal(result.ok, true, result.error);
    assert.equal(result.formatted, expected);
  }
});

test('formats untitled XML with Unicode cursor, CRLF and idempotence', () => {
  const result = invoke({ parser: 'xml', cursorOffset: source.indexOf('中文'), endOfLine: 'crlf' });
  assert.equal(result.ok, true, result.error);
  assert.equal(result.formatted, expected.replace('\n', '\r\n'));
  assert.equal(result.formatted.slice(result.cursorOffset, result.cursorOffset + 2), '中文');
  const repeated = invoke({ parser: 'xml', text: result.formatted, cursorOffset: result.cursorOffset });
  assert.equal(repeated.formatted, result.formatted);
  assert.equal(repeated.cursorOffset, result.cursorOffset);
});

test('preserves XML mixed text, entities, CDATA and comments by default', () => {
  const text = '<r>Hello <b>中文😀</b> world &amp; x<![CDATA[<raw>]]><!-- keep --></r>';
  const result = invoke({ parser: 'xml', text });
  assert.equal(result.formatted, text + '\n', result.error);
});

test('honors XML project options, config parser and explicit language overrides', (t) => {
  const dir = project(t);
  const filePath = path.join(dir, 'example.xml');
  const config = path.join(dir, '.prettierrc.json');
  fs.writeFileSync(config, '{"xmlWhitespaceSensitivity":"ignore","tabWidth":4}');
  assert.equal(invoke({ filePath }).formatted, '<root>\n    <item name="中文😀" />\n</root>\n');
  fs.writeFileSync(config, '{"parser":"babel","semi":false}');
  assert.equal(invoke({ filePath, text: 'const a=1;' }).formatted, 'const a = 1\n');
  assert.equal(invoke({ filePath, parser: 'xml' }).formatted, expected);
  fs.writeFileSync(config, '{"parser":"xml"}');
  assert.equal(invoke({ filePath: path.join(dir, 'example.txt') }).formatted, expected);
});

test('resolves explicit XML package names alongside Prettier and supports plugin paths', (t) => {
  const dir = project(t);
  for (const plugin of ['@prettier/plugin-xml', xmlEntry]) {
    fs.writeFileSync(path.join(dir, '.prettierrc.json'), JSON.stringify({ plugins: [plugin] }));
    assert.equal(invoke({ filePath: path.join(dir, 'example.xml') }).formatted, expected);
  }
});

test('uses project XML packages, preserves their errors and respects explicit plugin objects', (t) => {
  const dir = project(t);
  const pkg = path.join(dir, 'node_modules/@prettier/plugin-xml');
  fs.mkdirSync(pkg, { recursive: true });
  fs.writeFileSync(path.join(pkg, 'package.json'), '{"main":"index.cjs"}');
  fs.writeFileSync(path.join(pkg, 'index.cjs'), 'throw new Error("Project XML plugin failed to load");');
  const filePath = path.join(dir, 'example.xml');
  const broken = invoke({ filePath });
  assert.match(broken.error, /Project XML plugin failed to load/);
  assert.notEqual(broken.code, 'MISSING_XML_PLUGIN');
  assert.notEqual(broken.canChooseParser, true);
  fs.writeFileSync(path.join(dir, '.prettierrc.mjs'),
    `import xml from ${JSON.stringify(pathToFileURL(xmlEntry).href)}; export default { plugins: [xml] };`);
  assert.equal(invoke({ filePath }).formatted, expected);
});

test('reports missing XML without blocking built-ins, overrides or ignored files', (t) => {
  const dir = project(t);
  const standalone = path.join(project(t, 'npp-xml-runtime-'), 'node_modules/prettier');
  fs.cpSync(prettierPath, standalone, { recursive: true });
  assert.equal(JSON.parse(fs.readFileSync(path.join(standalone, 'package.json'), 'utf8')).name, 'prettier');
  const request = { prettierPath: standalone, filePath: path.join(dir, 'example.xml') };
  for (const override of [{}, { filePath: undefined, parser: 'xml' }]) {
    const missing = invoke({ ...request, ...override });
    assert.equal(missing.code, 'MISSING_XML_PLUGIN', missing.error);
    assert.equal(missing.ok, false);
    assert.equal(missing.exitCode, 1);
    assert.equal(missing.formatted, undefined);
    assert.notEqual(missing.canChooseParser, true);
  }
  assert.equal(invoke({ ...request, parser: 'babel', text: 'const a=1;' }).formatted, 'const a = 1;\n');
  fs.writeFileSync(path.join(dir, '.prettierrc.json'), '{"plugins":["@prettier/plugin-xml"]}');
  assert.equal(invoke(request).code, 'MISSING_XML_PLUGIN');
  fs.writeFileSync(path.join(dir, '.prettierignore'), '*.xml\n');
  const ignored = invoke(request);
  assert.equal(ignored.ok, true, ignored.error);
  assert.equal(ignored.ignored, true);
});

test('reports XML syntax errors with language recovery and no replacement', () => {
  const result = invoke({ parser: 'xml', text: '<root><' });
  assert.equal(result.ok, false);
  assert.equal(result.exitCode, 1);
  assert.equal(result.formatted, undefined);
  assert.match(result.error, /SyntaxError/);
  assert.equal(result.canChooseParser, true);
});
