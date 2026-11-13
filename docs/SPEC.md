# NppFormatter: product direction and prototype specification

## Product direction

Repository: `npp-formatter`. Project, plugin menu, and DLL base name: `NppFormatter`.
The product is a configurable code formatter and text transformer for Notepad++,
inspired by Formatter for Sublime Text. Multiple external tools, configuration-based
extension, and language-specific workflows are the target; Prettier is the first
adapter. External formatters and their runtimes are installed by the user.

This document distinguishes the implemented 0.3.0 Prettier and Ruff integration from planned
capabilities. The target architecture below is a plan, not current functionality.

## Target architecture (planned)

| Module | Responsibility |
|---|---|
| Editor integration | Buffer snapshots, whole-document/selection operations, UI dispatch, caret mapping, undo, and stale-result checks |
| Tool definitions | Tool ID, applicable languages, executable, argument array, working directory, timeout, input/output strategy, and capability flags |
| Tool selection | Explicit tool selection, per-language defaults, project-level overrides, and dependency diagnostics |
| Generic process execution | Launch the selected executable, transfer input/output, interpret exit codes, capture diagnostics, time out, and cancel |
| Specialized adapters | Handle tool-specific behavior such as Prettier configuration resolution and UTF-16 cursor mapping |
| Pipelines | Execute stages sequentially and apply the final output once, only if every stage succeeds and the source snapshot is still current |

Ordinary command-line tools should be registered through data configuration.
Specialized adapters are reserved for behavior that a generic input/output contract
cannot express. Node.js belongs to the Prettier adapter's requirements; the generic
core must be able to execute tools that do not use Node.js. Do not require a Node.js
bridge for every tool. Each adapter declares whether it supports ranges and caret
mapping; unsupported operations must not silently be represented as supported.

## Implementation order (planned)

1. Generalize the current process runner and add tool definition/configuration
   loading. Preserve the current Prettier behavior and editor protections.
2. Integrate clang-format and Ruff alongside Prettier. Verify different runtime
   and argument conventions against the same process and result contract.
3. Add manual selection, per-language defaults, project overrides, executable
   discovery, and useful missing-dependency diagnostics.
4. Add selection formatting and format-on-save, with per-tool capability checks
   and explicit save ordering.
5. Add minifiers, text converters, and transactional sequential pipelines.

Stage acceptance: tools are selectable without rebuilding the DLL; one adapter's
missing runtime does not prevent another adapter from running; tool failure leaves
the buffer unchanged; a pipeline has one final undoable write and no intermediate
editor mutations. These criteria remain unverified until their stages are built.

## Current prototype scope

The implemented prototype is a lightweight C++ DLL with a Prettier-specific
JavaScript bridge and a native Ruff adapter for Python. The shared process runner
accepts an executable, argument vector, working directory and stdin. Prettier needs
user-installed Node.js and Prettier; Python needs only a user-installed Ruff executable.
None is included in the ZIP. Configurable tool definitions, selection formatting
and pipelines remain planned.

Implemented slices:

1. Bridge: explicit Prettier package directory, formatting, configuration,
   ignore rules, UTF-16 cursor offsets, structured errors. Test with real Prettier.
2. Native plugin: explicit node.exe/package paths, settings, background process,
   timeout, full-buffer formatting, one-step undo, stale-result rejection.
3. Build and isolated Notepad++ smoke test. Package only runtime plugin files.
4. Settings discovery: separate background Auto-detect buttons for Node.js and
   Prettier. Resolve Node shims to the actual executable and require Node.js 18+;
   prefer the saved document's nearest Prettier 3.x package over configured/global
   locations. No installation or project-code execution during discovery. Fill
   fields only; persist on Save, preserve old values on failure, cancel on close.
5. UI localization: query NPPM_GETNATIVELANGFILENAME after NPPN_READY and on
   NPPN_NATIVELANGCHANGED. Select English, Simplified Chinese, or Traditional Chinese
   (including Hong Kong); fall back to English for other host languages. Update
   menu labels by command ID without changing callbacks, shortcuts, or item state.
   Relabel open Settings controls without recreating them or changing unsaved input.
   Keep translation lookups on the UI thread; background detection returns data.
   Localize Settings validation, guidance, About, and status messages. Preserve
   external diagnostics and Windows-owned dialog buttons in their original language.
6. Optional Java support: load user-installed prettier-plugin-java for saved
   .java files, the Notepad++ Java language, and the Java picker entry. Honor
   configured parser plugins; otherwise search the project before the selected
   Prettier installation. Untitled documents use the latter location. Localize
   missing-dependency guidance, preserve load errors, and offer explicit language
   recovery for Java parse failures. Never bundle or install the optional package.
7. XML support: reuse optional package discovery for
   @prettier/plugin-xml. Recognize .xml, .svg, .xsd, .xsl, .xslt, .xaml, and .resx,
   the Notepad++ XML language, and the XML picker entry. Preserve the plugin's
   strict whitespace default; honor project overrides. Localize missing-package
   guidance and preserve the document on errors. Add dedicated JSONC, MDX, and
   Handlebars entries backed by Prettier's built-in jsonc, mdx, and glimmer parsers.
8. PHP, SQL, and Properties support: discover @prettier/plugin-php,
   prettier-plugin-sql, and prettier-plugin-properties using the same rules.
   Map the matching host languages and expose explicit picker choices. Persist
   SqlDialect with standard SQL as the default; invalid stored values fall back
   to that default. Apply it only to SQL using sql-formatter, before project
   configuration. Projects using node-sql-parser retain their database setting.
   Save commits the selection; Cancel discards it. Live UI translation preserves
   the current selection. Missing packages and syntax failures retain the text.
9. TOML and Shell support: discover prettier-plugin-toml and prettier-plugin-sh,
   map L_TOML/L_BASH, and expose picker entries. Require Node.js 20+ for TOML and
   Prettier 3.6+ for Shell. Persist ShellDialect with Bash as the default and
   POSIX sh, mksh, and Bats alternatives; project variant overrides it. Use
   Prettier's whole-document cursor mapping for Shell because its upstream AST
   contains non-node objects and byte positions. Never execute document scripts.
10. Environment check: inspect unsaved Settings paths on the cancellable detection
    worker. Report Node/Prettier versions and each optional package's availability,
    version, resolved path, and sample formatting errors. Use current saved-document
    project discovery and explicit plugins, retaining broken-copy errors. Show
    Node details even when Prettier fails. Clear results on path changes, preserve
    results through live translation, and never install packages or save settings.

11. Python support: call Ruff directly through the shared process runner. Route
    .py/.pyi/.pyw files, the host's Python language and an explicit Python picker
    choice to Ruff without requiring Node.js. Persist RuffPath; browse, detect
    project .venv/PATH installations and inspect versions/sample formatting from
    unsaved settings. Keep failures in one tool independent of the other's check.
    Saved buffers use Ruff configuration discovery and force-exclude; untitled
    buffers use isolated defaults and the editor EOL preference. Never lint, sort
    imports, run Python, or write source files. Preserve unchanged prefix/suffix
    caret positions and use a clamped UTF-16 line/column fallback within changes.
    Ruff 0.17.5 is the tested version; x86 editor tests use x64 Ruff on x64 Windows,
    and ARM64 CI uses ARM64 Ruff. Native 32-bit Windows is outside this adapter's
    verified scope. Svelte/Astro/Pug are deferred; C/C++ is the next language priority.

The supported build targets are Notepad++ x86, x64, and ARM64 with UTF-8 Scintilla buffers. Existing non-UTF-8
buffers receive a clear message asking the user to convert the encoding first.
Saved files infer their parser from the path and project configuration. Untitled
files use a supported Notepad++ document language, a remembered document choice,
or plain-text JSON detection before prompting. Whole-text replacement clears the
remembered choice; ordinary edits and formatter writeback preserve it. The
language override command applies only to the current operation.
Only one formatting request is active at a time. Background results are applied
only if document identity, modification generation, and current contents match.
Switching documents discards a pending result. A changed selection is preserved
by discarding that result too. An unchanged formatted result creates no undo item.

## Files and commands

- src/: C++17 Win32 implementation; bridge/: CommonJS bridge.
- tests/: node:test integration tests, native smoke harness.
- third_party/: upstream SDK headers and JSON header, with provenance.
- scripts/build.ps1: LLVM-MinGW build and packaging for x86, x64, ARM64, or all.
- scripts/bootstrap.py: download the SHA-256-pinned build-only toolchain.
- scripts/verify_package.py: check PE machine, exports, imports, and ZIP payloads.
- `npm ci` then `npm test`: development dependencies and bridge tests.
- `powershell -ExecutionPolicy Bypass -File scripts/build.ps1`: build/package.

## Engineering conventions

Use explicit ownership for Win32 handles and UI-thread-only editor calls. Check
process creation, pipe I/O, timeout, encoding conversion, and parser errors.
Keep stdout exclusively for the JSON response; direct bridge diagnostics to stderr.
Example naming: `runBridge`, `FormatRequest`, `request.documentId`.

Always test changes at the real process boundary. Do not overwrite user files,
install into the user's active editor, download runtime dependencies at format
time, or bundle node_modules. Preserve third-party license notices. Ask before
publishing externally or replacing an existing user installation.

## Current prototype acceptance

- Format JSON/JS containing Chinese and emoji; preserve cursor by converting
  Scintilla UTF-8 byte positions to/from Prettier UTF-16 positions.
- Respect a project's config and nearest .prettierignore for a saved file.
- Format Java with the optional package; retain original text on missing or
  broken dependencies, and allow retry after installation without restarting.
- Apply the same dependency behavior to XML. Preserve mixed text, entities,
  CDATA, Unicode cursor positions, and LF/CRLF; follow project whitespace options.
- Exercise XML and the JSONC/MDX/Handlebars picker entries in the real editor.
- Exercise PHP, SQL, and Properties discovery, picker choices, saved files,
  localized missing dependencies, installation retry, and single undo. Verify
  SQL dialect persistence, Cancel, live translation, and project precedence.
- Exercise TOML and Shell extension/host/picker discovery, missing packages,
  real native/WASM loading, comments, heredocs, Unicode/CRLF cursor mapping,
  Shell dialect persistence and project precedence, and read-only environment
  diagnostics with unsaved paths, cancellation, missing/broken packages and locale changes.
- Error/timeout/invalid response/stale result leaves original text untouched.
- Python formatting works with empty Node/Prettier paths. Verify Ruff-only Save,
  Cancel, version/sample checks, project discovery, missing-tool translations,
  saved/untitled/picker/override routes, Unicode caret fallback, undo, no-op,
  invalid syntax/configuration and unchanged source files with a real Ruff process.
- One undo restores the previous text; a no-op leaves the undo stack untouched.
- Editor remains responsive while a child process is running.
- ZIP contains no Node.js runtime or Prettier package.
- Each architecture produces a separate ZIP and SHA-256 sidecar; all ZIPs use
  the same internal NppFormatter folder. The DLL must match the editor architecture.
- CI runs native process and editor tests on matching Windows hosts, including
  ARM64. Cross-builds on x64 explicitly skip ARM64 runtime tests, while PE and ZIP
  validation still run. A skipped runtime test is not a pass.

## Backlog

The five implementation stages above are the primary backlog. Worker reuse,
additional package managers, legacy buffer encodings,
incremental replacement for bookmarks/folding, and settings accessibility/DPI
testing are later increments. Keep the READMEs' implemented/planned labels aligned
with actual code and verification evidence as each stage lands.
