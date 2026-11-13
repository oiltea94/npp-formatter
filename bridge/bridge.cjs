'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { createRequire } = require('node:module');
const { format } = require('node:util');
const { spawnSync } = require('node:child_process');

// Project configuration may log messages. stdout belongs to the protocol.
console.log = (...args) => process.stderr.write(format(...args) + '\n');
console.info = console.log;
console.debug = console.log;

function findPrettier(directory) {
  if (typeof directory !== 'string' || !path.isAbsolute(directory)) return undefined;
  try {
    const metadata = JSON.parse(fs.readFileSync(path.join(directory, 'package.json'), 'utf8'));
    if (metadata.name !== 'prettier' || typeof metadata.version !== 'string' ||
        !/^3\.\d+\.\d+(?:[-+].*)?$/.test(metadata.version)) return undefined;
    require.resolve(directory); // Check the entry exists without loading package code.
    return fs.realpathSync(directory);
  } catch { return undefined; }
}

function detectPrettier(request) {
  if (request.filePath && !path.isAbsolute(request.filePath)) throw new Error('filePath must be absolute.');
  if (request.filePath) {
    let dir = path.dirname(request.filePath);
    while (true) {
      const found = findPrettier(path.join(dir, 'node_modules', 'prettier'));
      if (found) return { ok: true, prettierPath: found };
      const parent = path.dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  }
  const current = findPrettier(request.prettierPath);
  if (current) return { ok: true, prettierPath: current };

  // Invoke npm's JS entry with the selected Node; no shell, downloads or installs.
  const nodeDir = path.dirname(process.execPath);
  const appData = process.env.APPDATA;
  const directories = [nodeDir, appData && path.join(appData, 'npm'),
    ...(process.env.PATH ?? '').split(path.delimiter).map(dir => dir.replace(/^"|"$/g, ''))];
  const tried = new Set();
  for (const directory of directories) {
    if (!directory || !path.isAbsolute(directory)) continue;
    let cli;
    try { cli = fs.realpathSync(path.join(directory, 'node_modules/npm/bin/npm-cli.js')); }
    catch { continue; }
    if (tried.has(cli)) continue;
    tried.add(cli);
    const result = spawnSync(process.execPath, [cli, 'root', '--global'], {
      encoding: 'utf8', timeout: 2500, maxBuffer: 1024 * 1024, windowsHide: true,
    });
    if (!result.error && result.status === 0 && result.stdout.trim()) {
      const found = findPrettier(path.join(result.stdout.trim(), 'prettier'));
      if (found) return { ok: true, prettierPath: found };
    }
    if (tried.size >= 2) break;
  }
  // These locations also work for a portable Node installation without npm.
  const roots = [process.env.npm_config_prefix, appData && path.join(appData, 'npm'), nodeDir];
  for (const root of roots) {
    if (!root || !path.isAbsolute(root)) continue;
    const found = findPrettier(path.join(root, 'node_modules/prettier'));
    if (found) return { ok: true, prettierPath: found };
  }
  throw new Error('Prettier 3.x was not found. Install it in your project or globally, or use Browse.');
}

function nearestIgnore(filePath) {
  let dir = path.dirname(filePath);
  while (true) {
    const candidate = path.join(dir, '.prettierignore');
    if (fs.existsSync(candidate)) return candidate;
    const parent = path.dirname(dir);
    if (parent === dir) return undefined;
    dir = parent;
  }
}

const optionalPlugins = [
  { parser: 'java', name: 'prettier-plugin-java', code: 'MISSING_JAVA_PLUGIN', extensions: ['.java'] },
  { parser: 'xml', name: '@prettier/plugin-xml', code: 'MISSING_XML_PLUGIN',
    extensions: ['.xml', '.svg', '.xsd', '.xsl', '.xslt', '.xaml', '.resx'] },
];

function resolveOptionalPlugin(dependency, fromFiles) {
  for (const from of new Set(fromFiles.filter(Boolean))) {
    const resolver = createRequire(from);
    try { return resolver.resolve(dependency.name); }
    catch (error) {
      const installed = resolver.resolve.paths(dependency.name).some(root => fs.existsSync(path.join(root, dependency.name)));
      if (error.code !== 'MODULE_NOT_FOUND' || installed) throw error;
    }
  }
  const error = new Error(`Install ${dependency.name} in the project or alongside the configured Prettier package.`);
  error.code = dependency.code;
  throw error;
}

async function addOptionalPlugin(dependency, plugins, fromFiles) {
  // Respect project-supplied parsers, including plugin objects and custom paths.
  for (let i = 0; i < plugins.length; ++i) {
    if (typeof plugins[i] === 'string') {
      const imported = await import(pathToFileURL(plugins[i]).href);
      plugins[i] = imported.default ?? imported;
    }
    if (plugins[i]?.parsers?.[dependency.parser]) return;
  }
  const imported = await import(pathToFileURL(resolveOptionalPlugin(dependency, fromFiles)).href);
  const plugin = imported.default ?? imported;
  if (!plugin.parsers?.[dependency.parser])
    throw new Error(`The installed ${dependency.name} does not provide a ${dependency.parser} parser.`);
  plugins.push(plugin);
}

async function run(request) {
  if (request?.operation === 'detectNode') {
    if (Number(process.versions.node.split('.')[0]) < 18) throw new Error('Node.js 18 or later is required.');
    return { ok: true, nodePath: process.execPath, version: process.versions.node };
  }
  if (request?.operation === 'detectPrettier') return detectPrettier(request);
  if (!request || typeof request.text !== 'string') throw new Error('text must be a string.');
  if (!Number.isInteger(request.cursorOffset) || request.cursorOffset < 0 ||
      request.cursorOffset > request.text.length) throw new Error('Invalid UTF-16 cursorOffset.');
  if (typeof request.prettierPath !== 'string' || !path.isAbsolute(request.prettierPath)) {
    throw new Error('Set an absolute Prettier package directory in Settings.');
  }
  const packageFile = path.join(request.prettierPath, 'package.json');
  let metadata;
  try { metadata = JSON.parse(fs.readFileSync(packageFile, 'utf8')); }
  catch { throw new Error(`Prettier package.json was not found or is invalid: ${packageFile}`); }
  if (metadata.name !== 'prettier' || Number(metadata.version.split('.')[0]) !== 3) {
    throw new Error('This prototype requires a Prettier 3.x package directory.');
  }
  const entry = require.resolve(request.prettierPath);
  const imported = await import(pathToFileURL(entry).href);
  const prettier = imported.default ?? imported;
  const filePath = request.filePath;
  if (filePath !== undefined && (typeof filePath !== 'string' || !path.isAbsolute(filePath))) {
    throw new Error('filePath must be absolute.');
  }
  let parser = request.parser;
  if (!filePath && !parser) {
    if (request.detectParser === true) {
      try { JSON.parse(request.text); parser = 'json'; }
      catch { /* Ambiguous content requires a document-specific choice. */ }
    }
    if (!parser) return { ok: true, needsParser: true };
  }
  if (filePath) process.chdir(path.dirname(filePath));
  const config = filePath ? await prettier.resolveConfig(filePath, { editorconfig: true }) : null;
  const configFile = filePath ? await prettier.resolveConfigFile(filePath) : null;
  // Ignoring a file must not require installing its optional language dependency.
  if (filePath) {
    const info = await prettier.getFileInfo(filePath, {
      ignorePath: nearestIgnore(filePath), resolveConfig: false,
    });
    if (info.ignored) return { ok: true, ignored: true, version: prettier.version };
  }
  const plugins = (config?.plugins ?? []).map((plugin) => {
    if (typeof plugin !== 'string') return plugin;
    const from = configFile ?? filePath ?? packageFile;
    const dependency = optionalPlugins.find(item => item.name === plugin);
    if (dependency) return resolveOptionalPlugin(dependency, [from, packageFile]);
    return createRequire(from).resolve(plugin);
  });
  if (!parser && !config?.parser && filePath) {
    const extension = path.extname(filePath).toLowerCase();
    parser = optionalPlugins.find(item => item.extensions.includes(extension))?.parser;
  }
  const java = (parser ?? config?.parser) === 'java';
  const dependency = optionalPlugins.find(item => item.parser === (parser ?? config?.parser));
  if (dependency) await addOptionalPlugin(dependency, plugins, [filePath, configFile, packageFile]);
  const options = {
    endOfLine: request.endOfLine ?? 'auto', ...config, plugins,
    filepath: filePath, cursorOffset: request.cursorOffset,
  };
  if (parser) options.parser = parser;
  try {
    const result = await prettier.formatWithCursor(request.text, options);
    return { ok: true, ...result, version: prettier.version, configFile };
  } catch (error) {
    process.exitCode = 1;
    return {
      ok: false, error: `${error.name}: ${error.message}`,
      canChooseParser: Boolean(error.loc || error.name === 'SyntaxError' || error.name === 'UndefinedParserError' ||
        (java && error.name === 'Error' && error.message.startsWith('Failed to parse:'))),
    };
  }
}

(async () => {
  try {
    const chunks = [];
    let size = 0;
    for await (const chunk of process.stdin) {
      size += chunk.length;
      if (size > 64 * 1024 * 1024) throw new Error('Request exceeds 64 MiB.');
      chunks.push(chunk);
    }
    const request = JSON.parse(Buffer.concat(chunks).toString('utf8'));
    process.stdout.write(JSON.stringify(await run(request)));
  } catch (error) {
    process.stdout.write(JSON.stringify({ ok: false, error: `${error.name}: ${error.message}`, code: error.code }));
    process.exitCode = 1;
  }
})();
