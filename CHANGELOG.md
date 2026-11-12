# Changelog / 更新日志

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
