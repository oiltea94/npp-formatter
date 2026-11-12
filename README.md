<h1 align="center">NppFormatter</h1>

<p align="center">A configurable code formatter and text transformer for Notepad++.</p>

<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-x86%20%7C%20x64%20%7C%20ARM64-0078D4" alt="Windows x86, x64 and ARM64">
  <img src="https://img.shields.io/badge/status-0.1.0%20prototype-orange" alt="Version 0.1.0 prototype">
  <img src="https://img.shields.io/badge/current%20adapter-Prettier%203.x-F7B93E" alt="Current prototype adapter: Prettier 3.x">
</p>

<p align="center">
  <a href="#tool-support">Tool support</a> ·
  <a href="#installation">Installation</a> ·
  <a href="#usage">Usage</a> ·
  <a href="#troubleshooting">Troubleshooting</a> ·
  <a href="#build-from-source">Build from source</a>
</p>

Inspired by [Formatter for Sublime Text](https://packages.sublimetext.com/packages/Formatter), NppFormatter aims to bring multiple formatting and text transformation tools into one configurable Notepad++ plugin. It is an independent project; Prettier is the first integration.

> **Available today:** version 0.1.0 is a prototype for x86, x64, and ARM64 that formats whole documents with Prettier. Other tool adapters, generic tool definitions, text transformations, and tool pipelines are planned, not implemented. The installation and usage instructions below describe the working Prettier prototype.

### Current capabilities

- **Use your own dependencies**: configure an existing Node.js executable and Prettier package for the current adapter. Neither dependency is bundled or installed by the plugin.
- **Follow project rules**: saved files use their Prettier configuration, EditorConfig settings, and the nearest `.prettierignore`.
- **Keep editing**: formatting runs in a background process; results are discarded when the document changes during a request.
- **Undo in one step**: formatting replaces the document in place, preserves the caret and scroll position, and can be reverted with **Ctrl+Z**. Unchanged output adds no undo entry.

## Tool support

| Tool or capability | Status | Intended role |
|---|---|---|
| Prettier | Implemented in the prototype | Full-document formatting with project configuration |
| clang-format | Planned adapter | C/C++ formatting |
| Ruff | Planned adapter | Python formatting |
| User-defined command-line tools | Planned | Register tools through configuration, including applicable languages, executable paths, arguments, working directories, and timeouts |
| Minifiers and text converters | Planned | Additional tool-driven text transformations |
| Tool pipelines | Planned | Run tools in order and apply the final result once |

External tools are installed by the user. In the target architecture, runtime dependencies belong to each adapter: Node.js is required for Prettier, not for the generic plugin core. **The current prototype still requires Node.js and Prettier**, because it only implements that adapter.

## Example

**Before — JavaScript**

```javascript
function greet(name){return "Hello, "+name;}
```

**After — Prettier defaults**

```javascript
function greet(name) {
  return "Hello, " + name;
}
```

Project configuration can change quotes, semicolons, indentation, and line endings.

## Requirements

These requirements apply to the **current Prettier prototype**. Future adapters will have their own tool requirements.

| Component | Requirement |
|---|---|
| Editor | **Notepad++ x86, x64, or ARM64** on Windows |
| Node.js | User-installed **18 or later** |
| Prettier | User-installed **3.x** |
| Document | UTF-8 editor buffer, up to **8 MiB**, with one ordinary caret or selection |

Match the plugin to the architecture of **Notepad++**, not just Windows. For example, 32-bit Notepad++ on 64-bit Windows needs the x86 package. Node.js runs as a separate process: it must run on your Windows installation, but need not match the plugin's architecture. Compatibility across editor and dependency versions still needs broader testing.

| Notepad++ architecture | Package |
|---|---|
| x86 (32-bit) | `NppFormatter-0.1.0-x86.zip` |
| x64 (64-bit) | `NppFormatter-0.1.0-x64.zip` |
| ARM64 | `NppFormatter-0.1.0-arm64.zip` |

## Installation

### 1. Install the Prettier adapter dependencies

Install Node.js, then install Prettier using **one** of these approaches.

**Project installation** — run from your project directory:

```powershell
npm install --save-dev --save-exact prettier@3
```

**Global installation** — convenient for formatting files across projects:

```powershell
npm install --global prettier@3
```

The prototype always uses the package directory selected in Settings. It does not automatically switch to a different project's Prettier installation.

### 2. Install the plugin

1. Obtain the ZIP matching your Notepad++ architecture from the table above. Building this repository produces packages under `dist/`; see [Build from source](#build-from-source).
2. Close Notepad++. If `plugins/NppFormatter` already exists, rename it as a backup before upgrading.
3. Extract the ZIP and copy its `NppFormatter` folder into Notepad++'s `plugins` directory.
4. Restart Notepad++ and open **Plugins → NppFormatter → Settings...**.

```text
Notepad++/
└── plugins/
    └── NppFormatter/
        ├── NppFormatter.dll
        ├── bridge.cjs
        ├── README.md
        ├── README.zh-CN.md
        └── licenses/
```

Keep `bridge.cjs` beside the DLL; copying only the DLL is not sufficient.

### 3. Configure the paths

Click **Auto-detect** to the right of each **Browse...** button: detect Node.js first, then Prettier. Detection fills the fields; click **Save** to persist them. A failed detection keeps the previous path, and **Cancel** discards unsaved changes, including while detection is running.

- **Node.js:** searches `PATH`, common installation locations, NVM/Volta locations, and the existing field. It probes candidates for Node.js 18+ and uses the actual executable path returned by Node.js.
- **Prettier:** uses the Node.js field; searches the current saved file's directory and ancestors for `node_modules/prettier`, then the existing field, npm's global root (including custom prefixes), and common global locations. It accepts Prettier 3.x packages with a resolvable entry. Detection does not load project configuration or run Prettier package code.

Detection runs in the background without installing dependencies. For an unsaved document, the project-directory search is skipped. If detection finds nothing, install the dependency or select it with **Browse...**. Restart Notepad++ after changing `PATH`. Detecting a project package does not enable automatic switching between projects.

To locate the paths manually:

Find the actual Node.js executable:

```powershell
node -p "process.execPath"
```

For a **project installation**, run this from that project directory:

```powershell
node -p "require('path').dirname(require.resolve('prettier/package.json'))"
```

For a **global installation**, get the package directory with:

```powershell
Join-Path (npm root -g) 'prettier'
```

| Setting | Value |
|---|---|
| Node.js executable | Absolute path to `node.exe` |
| Prettier package directory | Absolute directory containing Prettier's `package.json`; Browse selects that file and fills in its directory |
| Timeout in milliseconds | Defaults to `10000` (10 seconds); accepts `1000`–`120000` |

Click **Save**. Select the package directory itself, not its `bin` directory or a `prettier.cmd` launcher.

## Usage

### Interface language

The plugin follows **Notepad++'s interface language**, independently of the Windows display language. English, Simplified Chinese, and Traditional Chinese are supported; the Hong Kong Chinese locale uses Traditional Chinese. Other locales fall back to English.

Menus, Settings labels/buttons, detection guidance, settings validation messages, About, and formatting status messages are translated. Changing the language in Notepad++ Preferences updates the plugin menu and an open Settings window immediately, preserving unsaved fields and the current detection operation. No separate language setting or restart is required. External tool diagnostics remain in their original language; Windows supplies the standard file-picker and message-box buttons.

| English | Simplified Chinese | Traditional Chinese |
|---|---|---|
| Format document | 格式化文档 | 格式化文件 |
| Settings... | 配置... | 設定... |
| About | 关于 | 關於 |
| Auto-detect | 自动检测 | 自動偵測 |

### Formatting

Select **Plugins → NppFormatter → Format document**. To assign a shortcut, locate the command under **Settings → Shortcut Mapper → Plugin commands**.

| Menu command | Behavior |
|---|---|
| Format document | Format the entire current buffer, including unsaved edits |
| Settings... | Configure dependency paths and timeout |
| About | Show the plugin version and runtime requirements |

- **Saved documents:** the file path is passed to Prettier for parser inference and configuration lookup. Common built-in formats include JavaScript, TypeScript, JSON, HTML, CSS, Markdown, and YAML.
- **Untitled documents:** the formatter follows the document language selected in Notepad++ for JavaScript, TypeScript, JSON, JSON5, HTML, CSS, and YAML. For plain text, valid JSON is detected automatically in the background. Otherwise, a language picker appears when you format; its choice is remembered only for that document during the current session. Closing or saving the document, or changing its language in Notepad++, clears the choice. Cancel leaves the text unchanged. These documents have no project path for configuration lookup.
- **Existing settings:** the old global `UntitledParser` value is ignored and removed the next time settings are saved; dependency paths and timeout are retained. To correct a document's remembered choice, select its language in Notepad++ (or switch to another language and back to plain text to choose again).
- **Selections:** the command still formats the whole document. After replacement, an ordinary selection collapses to the mapped caret. Multiple carets and rectangular selections are not supported in this prototype.
- **While formatting:** editing, switching documents, saving, or changing the caret/selection can cause the pending result to be discarded. Run the command again once you are ready.
- **Failures:** syntax errors, missing dependencies, and timeouts leave the original text intact. The status bar reports progress, ignored files, unchanged output, and discarded results.

### Project configuration

For saved documents, the bridge loads Prettier configuration with EditorConfig support and checks the nearest `.prettierignore` found by walking up from the file's directory.

Example `.prettierrc`:

```json
{
  "singleQuote": true,
  "semi": false,
  "tabWidth": 2
}
```

Files matching the ignore rules are skipped. The document's LF or CRLF setting is used unless project configuration overrides it. JavaScript-based configuration and additional Prettier plugins may require a newer Node.js version or extra project dependencies.

## Troubleshooting

| Symptom | What to check |
|---|---|
| NppFormatter is missing from the menu | Match the DLL architecture to Notepad++, check the folder structure, and restart the editor |
| Formatting opens Settings | Configure both dependency paths before the first request |
| Node.js does not start | Use the actual absolute `node.exe` path returned by `process.execPath` |
| Prettier cannot be loaded | Select a Prettier 3.x package directory containing `package.json`, not `prettier.cmd` |
| An untitled document gives a syntax error | Check its language in Notepad++; change the language to clear a remembered choice, or save it with a suitable extension |
| A saved file gives a parser or syntax error | Check its extension, contents, and project configuration |
| A file is skipped or a result is discarded | Check `.prettierignore`; rerun formatting after editing or switching documents |
| Formatting times out | Inspect project config/plugins and increase the timeout if needed |
| The plugin asks for UTF-8 | Select **Encoding → Convert to UTF-8**, then retry |
| A document or selection is rejected | Keep the buffer within 8 MiB and use one ordinary caret or selection |

Formatting replaces the entire buffer. Bookmarks and folding positions may move; incremental replacement is not implemented. The settings window's high-DPI and screen-reader behavior still needs release testing.

## Settings, upgrades, and uninstalling

Settings are stored in `NppFormatter.ini` inside the plugin configuration directory supplied by Notepad++. Saving existing settings creates `NppFormatter.ini.bak` containing the previous version. Close the settings window and copy the backup over the INI to restore it; the next formatting request reloads the file.

To upgrade, close Notepad++, back up `plugins/NppFormatter`, and copy in the new folder. To roll back, close the editor and restore the previous folder. To uninstall, remove `plugins/NppFormatter` while Notepad++ is closed. Keep the INI for a future installation or remove it separately.

## Build from source

Build tools: **LLVM-MinGW 20261104 (UCRT)**, Node.js, npm, **Python 3.12+**, and PowerShell. The pinned compiler runs on Windows x64 (or Windows 11 ARM64 using x64 emulation) and cross-compiles all three targets. It replaces the earlier Zig-only build.

From the repository root:

```powershell
npm ci
python scripts/bootstrap.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Architecture all
```

The bootstrap downloads the pinned compiler and verifies its SHA-256 before extraction. To use an existing LLVM-MinGW installation, pass its root with `-Toolchain` or set `LLVM_MINGW_ROOT`. `-Architecture` accepts `x86`, `x64` (default), `arm64`, or `all`.

The build runs the bridge tests and native process tests where the host can execute the target. On x64 Windows, ARM64 runtime tests are explicitly skipped; cross-compilation alone is not a runtime pass. `-SkipTests` skips bridge/native execution but always verifies the package. Each ZIP is checked for its PE architecture, six Notepad++ exports, system-only DLL imports, and exact contents. Outputs use `build/<arch>` and `dist/<arch>/NppFormatter`; ZIPs and SHA-256 sidecars are written to `dist/`.

The ZIP contains the DLL, bridge script, both READMEs, and third-party license notices. Node.js, Prettier, tests, and build tools stay outside the package; `npm ci` installs Prettier only as a development test dependency.

| Command | Purpose |
|---|---|
| `npm test` | Test formatting, configuration, ignore rules, Unicode cursor offsets, and errors using real Prettier |
| `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1` | Build x64, run bridge/native tests, and package the plugin |
| `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Architecture all` | Build and package x86, x64, and ARM64 |
| `python -m unittest discover -s tests -p test_artifacts.py` | Verify rejection of wrong architectures, missing exports, extra files, and stale ZIP contents after building |
| `python tests/editor_smoke.py --arch x64` | Test the selected architecture in an isolated copy of Notepad++ |

The smoke test locates Notepad++ through `NPP_EXE`, `PATH`, or the standard installation location and checks its architecture before launch. It runs a separate copy in an automatically cleaned temporary directory and checks formatting, caret mapping, undo, no-op behavior, and stale-result protection. Its result summary omits machine-specific paths. Use 64-bit Python for x64/ARM64 editor tests.

CI builds x86 and x64 on `windows-latest`, and ARM64 on `windows-11-arm`. Each job runs native process tests and the matching portable editor test before uploading a ZIP and checksum. The portable test editor is pinned to Notepad++ 8.9.6 with a SHA-256 check. Workflow configuration alone does not establish a test pass; inspect the run for each architecture. No release is published automatically.

Code is split between `src/` (native plugin and process management), `bridge/` (Prettier integration), and `tests/`. The prototype runs one Node.js process per request and allows one active request at a time.

Editor tests run in English, Simplified Chinese, and Traditional Chinese by default. Use `--language en`, `--language zh-CN`, or `--language zh-TW` to select one. The portable test editor must include the corresponding official localization XML files; `tests/download_npp.py` extracts them from the hash-verified archive. Tests also switch languages through Notepad++ Preferences with unsaved Settings fields. Translations are centralized in `src/i18n.hpp`; CI runs all three languages for every CPU architecture.

## Roadmap and contributing

The next implementation stages are:

1. **Generic tool execution and configuration:** separate process management from the Prettier adapter; define tool IDs, language mappings, executable paths, argument arrays, working directories, timeouts, and input/output handling.
2. **Multiple adapters:** retain Prettier's configuration and caret mapping, then integrate clang-format and Ruff to validate the common execution model.
3. **Tool selection and diagnostics:** add explicit selection, language defaults, project overrides, dependency discovery, and actionable environment checks.
4. **Editor workflows:** add selection formatting and format on save, with tool-specific capabilities and the existing undo/stale-result protections.
5. **Transformations and pipelines:** support minifiers, converters, and sequential tools; apply the final output in one undoable change only after every stage succeeds.

Worker reuse, additional encodings, and improved bookmark/folding preservation are later work. See `docs/SPEC.md` in the source checkout for the target architecture and the current prototype's acceptance criteria.

For a bug report, include the plugin, Notepad++, Node.js, and Prettier versions; a minimal input; relevant configuration; the expected result; and the exact error or status message. For code changes, run the relevant tests and keep both READMEs in sync.

---

Third-party source versions and notices are recorded in `third_party/README.md` in the source checkout. Installed packages include the notices in `licenses/`.
