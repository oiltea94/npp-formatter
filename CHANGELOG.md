# Changelog / 更新日志

## Unreleased / 尚未发布

No pending changes. / 暂无待发布改动。

## 0.3.0

### English

#### Added

- Add Python formatting through user-installed Ruff, independently of Node.js and Prettier. Recognize `.py`, `.pyi`, `.pyw`, Notepad++ Python, and a Python language-picker entry.
- Add Ruff browsing, project/PATH detection, saved settings, and independent version/sample checks in English, Simplified Chinese, and Traditional Chinese.
- Honor saved-file Ruff configuration and exclusions; isolate untitled defaults. Preserve source files, error text, one-step undo, and stale-result protection. Use an approximate line/column fallback for the caret in changed regions.
- Verify Ruff 0.17.5 with x86/x64/ARM64 plugin builds; native ARM64 CI uses ARM64 Ruff. Tools remain user-installed and are never bundled.

#### Fixed

- Fix a UTF-8 text snapshot race in editor smoke tests and add deterministic regression checks.

### 中文

#### 新增

- 通过用户自行安装的 Ruff 格式化 Python，不依赖 Node.js 或 Prettier。识别 `.py`、`.pyi`、`.pyw`、Notepad++ Python 语言及 Python 语言选择器选项。
- 新增 Ruff 路径浏览、项目／PATH 自动检测、配置保存及独立的版本和样本检查，覆盖英文、简体中文和繁体中文。
- 已保存文件遵循 Ruff 配置与排除规则，未保存文档使用隔离默认值。保留源文件、原始错误、一步撤销和过期结果保护；变化区域的光标使用近似行列定位。
- 使用 Ruff 0.17.5 验证 x86、x64、ARM64 插件；ARM64 CI 使用原生 ARM64 Ruff。外部工具仍由用户自行安装，不随包附带。

#### 修复

- 修复编辑器冒烟测试读取 UTF-8 文本时的竞态，并加入确定性回归测试。

## 0.2.0

### English

#### Added

- Add TOML and Shell / Bash formatting using separately installed `prettier-plugin-toml` and `prettier-plugin-sh`. TOML requires Node.js 20+; Shell requires Prettier 3.6+.
- Add a saved Shell dialect setting (Bash, POSIX sh, mksh, Bats), with project configuration taking priority.
- Add **Check formatting environment** in Settings: inspect entered paths, versions, and seven optional language packages using real formatting samples, without installing dependencies or saving settings.
- Preserve the Shell cursor through whole-document mapping, including Unicode and CRLF, avoiding upstream AST position failures.
- Add optional PHP, SQL, and Properties formatting with user-installed npm packages, automatic discovery, and localized install-and-retry guidance.
- Add a persistent SQL dialect setting; saved documents prioritize project configuration, and unsaved selections survive live interface language changes.
- Format XML, SVG, XSD, XSL/XSLT, XAML, and RESX with the separately installed `@prettier/plugin-xml` package. Discover it automatically and preserve XML whitespace semantics by default.
- Add dedicated JSONC, MDX, and Handlebars choices using Prettier's built-in parsers.
- Explain the optional XML dependency in English, Simplified Chinese, and Traditional Chinese, including install-and-retry guidance.

### 中文

#### 新增

- 通过单独安装的 `prettier-plugin-toml` 和 `prettier-plugin-sh` 支持 TOML 与 Shell / Bash；TOML 需要 Node.js 20+，Shell 需要 Prettier 3.6+。
- 新增可保存的 Shell 方言设置（Bash、POSIX sh、mksh、Bats），项目配置优先。
- 配置窗口新增**检查格式化环境**：使用真实格式化样本检查当前输入的路径、版本和七种可选语言扩展，不安装依赖、不保存配置。
- 使用全文映射保留 Shell 光标位置，覆盖 Unicode 和 CRLF，避开上游语法树位置错误。
- 通过用户自行安装的 npm 扩展支持 PHP、SQL 和 Properties，自动查找依赖并提供三语安装重试提示。
- 新增可保存的 SQL 方言设置，已保存文档优先遵循项目配置，切换界面语言时保留尚未保存的选择。
- 通过单独安装的 `@prettier/plugin-xml` 扩展支持 XML、SVG、XSD、XSL/XSLT、XAML 和 RESX，自动查找扩展，默认保留 XML 空白语义。
- 新增 JSONC、MDX 和 Handlebars 独立语言选项，使用 Prettier 内置解析器。
- 在英文、简体中文和繁体中文界面中说明 XML 可选依赖，并提供安装后重试的提示。

## 0.1.0

Initial prototype for Notepad++ on Windows x86, x64, and ARM64.

- Format whole documents with user-installed Node.js and Prettier, following project configuration and ignore rules.
- Support Java with the optional, separately installed `prettier-plugin-java` package.
- Detect dependency paths, select formatting languages, and recover from parser errors without changing the original text.
- Follow the editor's English, Simplified Chinese, or Traditional Chinese interface language.
- Run formatting in the background with one-step undo and protection against stale results.

面向 Windows x86、x64 和 ARM64 上 Notepad++ 的首个原型版本。

- 使用用户自行安装的 Node.js 和 Prettier 格式化全文，遵循项目配置和忽略规则。
- 通过单独安装的可选 `prettier-plugin-java` 扩展支持 Java。
- 自动检测依赖路径、选择格式化语言，并在解析失败时保留原文以便重试。
- 跟随编辑器的英文、简体中文或繁体中文界面。
- 后台执行格式化，支持单步撤销并防止过期结果写回。

Node.js, Prettier, and language plugins are not bundled. Other formatter adapters and selection formatting remain planned.

安装包不捆绑 Node.js、Prettier 或语言扩展包。其他格式化适配器和选区格式化仍在规划中。
