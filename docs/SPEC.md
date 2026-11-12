# NppFormatter: product direction and prototype specification

## Product direction

Repository: `npp-formatter`. Project, plugin menu, and DLL base name: `NppFormatter`.
The product is a configurable code formatter and text transformer for Notepad++,
inspired by Formatter for Sublime Text. Multiple external tools, configuration-based
extension, and language-specific workflows are the target; Prettier is the first
adapter. External formatters and their runtimes are installed by the user.

This document distinguishes the implemented 0.1.0 Prettier prototype from planned
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
JavaScript bridge. It currently requires user-installed Node.js and Prettier;
neither is included in the ZIP. It does not yet implement generic tool definitions,
additional adapters, selection formatting, or pipelines.

Implemented slices:

1. Bridge: explicit Prettier package directory, formatting, configuration,
   ignore rules, UTF-16 cursor offsets, structured errors. Test with real Prettier.
2. Native plugin: explicit node.exe/package paths, settings, background process,
   timeout, full-buffer formatting, one-step undo, stale-result rejection.
3. Build and isolated Notepad++ smoke test. Package only runtime plugin files.

The supported build targets are Notepad++ x86, x64, and ARM64 with UTF-8 Scintilla buffers. Existing non-UTF-8
buffers receive a clear message asking the user to convert the encoding first.
Saved files infer their parser from the path. For untitled files the user chooses
a parser in settings. Empty parser on an untitled file is an actionable error.
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
- Error/timeout/invalid response/stale result leaves original text untouched.
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
