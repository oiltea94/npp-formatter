'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { createRequire } = require('node:module');
const { format } = require('node:util');

// Project configuration may log messages. stdout belongs to the protocol.
console.log = (...args) => process.stderr.write(format(...args) + '\n');
console.info = console.log;
console.debug = console.log;

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

async function run(request) {
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
  if (!filePath && !request.parser) {
    throw new Error('Select an untitled-document parser in Settings, or save the document first.');
  }
  if (filePath) process.chdir(path.dirname(filePath));
  const config = filePath ? await prettier.resolveConfig(filePath, { editorconfig: true }) : null;
  const configFile = filePath ? await prettier.resolveConfigFile(filePath) : null;
  const plugins = (config?.plugins ?? []).map((plugin) => {
    if (typeof plugin !== 'string') return plugin;
    const from = configFile ?? filePath ?? packageFile;
    return createRequire(from).resolve(plugin);
  });
  if (filePath) {
    const info = await prettier.getFileInfo(filePath, {
      ignorePath: nearestIgnore(filePath), resolveConfig: false, plugins,
    });
    if (info.ignored) return { ok: true, ignored: true, version: prettier.version };
  }
  const options = {
    endOfLine: request.endOfLine ?? 'auto', ...config, plugins,
    filepath: filePath, cursorOffset: request.cursorOffset,
  };
  if (request.parser) options.parser = request.parser;
  const result = await prettier.formatWithCursor(request.text, options);
  return { ok: true, ...result, version: prettier.version, configFile };
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
    process.stdout.write(JSON.stringify({ ok: false, error: `${error.name}: ${error.message}` }));
    process.exitCode = 1;
  }
})();
