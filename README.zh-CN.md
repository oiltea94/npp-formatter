<h1 align="center">NppFormatter</h1>

<p align="center">可配置的 Notepad++ 代码格式化与文本转换插件。</p>

<p align="center"><a href="README.md">English</a> · <strong>简体中文</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-x86%20%7C%20x64%20%7C%20ARM64-0078D4" alt="Windows x86、x64 和 ARM64">
  <img src="https://img.shields.io/badge/status-0.1.0%20prototype-orange" alt="0.1.0 原型版本">
  <img src="https://img.shields.io/badge/current%20adapter-Prettier%203.x-F7B93E" alt="当前原型已接入：Prettier 3.x">
</p>

<p align="center">
  <a href="#工具支持">工具支持</a> ·
  <a href="#安装">安装</a> ·
  <a href="#使用">使用</a> ·
  <a href="#常见问题">常见问题</a> ·
  <a href="#从源码构建">从源码构建</a>
</p>

NppFormatter 的设计参考 [Sublime Text 的 Formatter](https://packages.sublimetext.com/packages/Formatter)，目标是在一个可配置的 Notepad++ 插件中接入多种格式化和文本转换工具。本项目独立开发，Prettier 是第一个接入的工具。

> **当前已实现：** 0.1.0 是通过 Prettier 格式化全文的原型，提供 x86、x64 和 ARM64 构建。其他工具适配器、通用工具配置、文本转换和工具串联属于后续计划，尚未实现。下面的安装与使用说明对应当前可运行的 Prettier 原型。

### 当前功能

- **使用已有依赖**：为当前适配器配置本机的 Node.js 可执行文件和 Prettier 包，插件不捆绑或安装这两项依赖。
- **遵循项目规则**：已保存文件使用项目的 Prettier 配置、EditorConfig 设置和最近的 `.prettierignore`。
- **保持编辑流畅**：格式化在后台进程中执行；请求期间文档发生变化时，丢弃过期结果。
- **一次撤销恢复**：在当前文档中替换格式化结果，保留光标和滚动位置；按 **Ctrl+Z** 即可恢复，内容未变化时不增加撤销记录。

## 工具支持

| 工具或能力 | 状态 | 用途 |
|---|---|---|
| Prettier | 原型已实现 | 按项目配置格式化全文 |
| clang-format | 计划接入 | C/C++ 格式化 |
| Ruff | 计划接入 | Python 格式化 |
| 用户自定义命令行工具 | 规划中 | 通过配置注册工具，指定适用语言、可执行文件、参数、工作目录和超时 |
| 压缩工具与文本转换工具 | 规划中 | 通过外部工具扩展文本处理能力 |
| 工具串联 | 规划中 | 按顺序执行多个工具，最后统一回写 |

外部工具由用户自行安装。在目标架构中，运行依赖归属于各个适配器：Prettier 需要 Node.js，通用插件核心不统一要求 Node.js。**当前原型仍需安装 Node.js 和 Prettier**，因为目前仅实现了这一种接入。

## 格式化示例

**格式化前 — JavaScript**

```javascript
function greet(name){return "Hello, "+name;}
```

**格式化后 — Prettier 默认设置**

```javascript
function greet(name) {
  return "Hello, " + name;
}
```

项目配置可以改变引号、分号、缩进和换行符。

## 环境要求

以下要求对应**当前 Prettier 原型**；未来的其他适配器会有各自的工具依赖。

| 组件 | 要求 |
|---|---|
| 编辑器 | Windows 下的 **Notepad++ x86、x64 或 ARM64** |
| Node.js | 用户自行安装 **18 或以上版本** |
| Prettier | 用户自行安装 **3.x** |
| 文档 | UTF-8 编辑缓冲区，最多 **8 MiB**，使用单个普通光标或选区 |

插件架构须匹配 **Notepad++**，不能只根据 Windows 架构选择。例如，64 位 Windows 上运行的 32 位 Notepad++ 应选择 x86 包。Node.js 在独立进程中运行，只需兼容当前 Windows，无需与插件架构一致。不同编辑器和依赖版本的兼容性仍需扩大验证。

| Notepad++ 架构 | 安装包 |
|---|---|
| x86（32 位） | `NppFormatter-0.1.0-x86.zip` |
| x64（64 位） | `NppFormatter-0.1.0-x64.zip` |
| ARM64 | `NppFormatter-0.1.0-arm64.zip` |

## 安装

### 1. 安装 Prettier 适配器依赖

安装 Node.js 后，用下面**任意一种方式**安装 Prettier。

**项目安装** — 在项目目录中运行：

```powershell
npm install --save-dev --save-exact prettier@3
```

**全局安装** — 便于格式化不同项目中的文件：

```powershell
npm install --global prettier@3
```

原型始终使用 Settings 中指定的包目录，不会随当前项目自动切换 Prettier 安装。

### 2. 安装插件

1. 按上表选择与 Notepad++ 架构一致的 ZIP。从本仓库构建后，安装包位于 `dist/`；参见[从源码构建](#从源码构建)。
2. 关闭 Notepad++。升级已有版本时，先将 `plugins/NppFormatter` 文件夹改名备份。
3. 解压 ZIP，将其中的 `NppFormatter` 文件夹复制到 Notepad++ 的 `plugins` 目录。
4. 重启 Notepad++，打开 **插件 → NppFormatter → Settings...**。

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

`bridge.cjs` 必须与 DLL 位于同一目录，安装时需要同时复制。

### 3. 配置路径

点击各行 **Browse...** 右侧的 **Auto-detect（自动检测）**：先检测 Node.js，再检测 Prettier。检测成功会填入输入框，点击 **Save** 才保存。检测失败保留原路径；**Cancel** 放弃未保存的修改，也可在检测期间取消。

- **Node.js**：查找 `PATH`、常见安装目录、NVM/Volta 目录和输入框中的现有路径。逐个验证候选是否为 Node.js 18+，并使用 Node.js 返回的真实可执行文件路径。
- **Prettier**：使用 Node.js 输入框中的程序，先从当前已保存文件所在目录逐级向上查找 `node_modules/prettier`，再检查现有路径、npm 全局目录（含自定义 prefix）及常见全局位置。仅接受入口可解析的 Prettier 3.x 包。检测不会加载项目配置或执行 Prettier 包代码。

检测在后台运行，不会安装依赖。未保存的文档跳过项目目录搜索；未找到时可先安装依赖，或通过 **Browse...** 手动选择。修改 `PATH` 后请重启 Notepad++。检测项目中的包不会启用跨项目自动切换。

手动查找路径的方法如下：

查询实际的 Node.js 可执行文件路径：

```powershell
node -p "process.execPath"
```

使用**项目安装**时，在对应项目目录中查询 Prettier 包路径：

```powershell
node -p "require('path').dirname(require.resolve('prettier/package.json'))"
```

使用**全局安装**时，运行以下命令获得包目录：

```powershell
Join-Path (npm root -g) 'prettier'
```

| 设置项 | 填写内容 |
|---|---|
| Node.js executable | `node.exe` 的绝对路径 |
| Prettier package directory | 包含 Prettier `package.json` 的绝对目录；Browse 选择该文件后会自动填入所在目录 |
| Timeout in milliseconds | 默认 `10000` 毫秒（10 秒），允许范围为 `1000`–`120000` |

点击 **Save** 保存。Prettier 路径应指向包本身的目录，避免选成 `bin` 目录或 `prettier.cmd` 启动脚本。

## 使用

### 界面语言

插件跟随 **Notepad++ 的界面语言**，不依赖 Windows 显示语言。支持英文、简体中文和繁体中文；香港中文语言使用繁体中文，其他语言暂时回退为英文。

插件菜单、配置窗口标签与按钮、检测引导、配置校验提示、关于内容和格式化状态提示均提供翻译。在 Notepad++ 首选项中切换语言后，插件菜单和已打开的配置窗口会立即更新，保留未保存的输入和正在进行的检测，无需单独设置插件语言或重启。外部工具的原始诊断保留原文；标准文件选择框和消息框按钮由 Windows 提供。

| 英文 | 简体中文 | 繁体中文 |
|---|---|---|
| Format document | 格式化文档 | 格式化文件 |
| Format with language... | 按指定语言格式化... | 依指定語言格式化... |
| Settings... | 配置... | 設定... |
| About | 关于 | 關於 |
| Auto-detect | 自动检测 | 自動偵測 |

### 格式化

选择 **插件 → NppFormatter → Format document**。需要快捷键时，在 **设置 → 管理快捷键（Shortcut Mapper）→ 插件命令（Plugin commands）** 中找到格式化命令并设置。

| 菜单命令 | 作用 |
|---|---|
| Format document | 格式化当前缓冲区全文，包含尚未保存的修改 |
| Settings... | 配置依赖路径和超时时间 |
| About | 查看插件版本和运行要求 |
| Format with language... | 选择仅本次生效的语言，适用于已保存文件；保留文件类型、记住的语言、项目选项及忽略规则 |

- **已保存文档**：将文件路径传给 Prettier，用于推断解析器和查找配置。常见内置格式包括 JavaScript、TypeScript、JSON、HTML、CSS、Markdown 和 YAML。
- **新建且尚未保存的文档**：优先跟随 Notepad++ 中选择的文档语言，支持 JavaScript、TypeScript、JSON、JSON5、HTML、CSS 和 YAML。纯文本中的有效 JSON 会在后台自动识别；其他情况在格式化时弹出语言选择窗口，选择仅在本次会话中为当前文档记住。整篇替换（包括清空后重新粘贴）、关闭、保存文档或切换 Notepad++ 文档语言后清除选择；普通编辑和插件自身的格式化写回会保留选择。取消选择保留原文。此类文档没有用于查找项目配置的文件路径。
- **已有配置**：旧的全局 `UntitledParser` 值不再使用，下次保存配置时移除；依赖路径与超时时间保留。如果当前文档记住了错误的选择，可在 Notepad++ 中选择正确语言，或切换到其他语言后再切回普通文本以重新选择。
- **选区处理**：命令仍会格式化全文；成功替换后，普通选区收拢到映射后的光标位置。原型暂不处理多光标和矩形选区。
- **格式化期间**：修改内容、切换文档、保存，或改变光标与选区，都可能使待返回结果被丢弃。停止这些操作后重新执行即可。
- **错误处理**：语法错误、依赖缺失或超时均保留原文。状态栏显示执行进度、忽略文件、内容未变化和结果被丢弃等状态。
- **解析失败后的恢复**：可点击“查看错误详情”检查原始诊断，也可点击“重新选择语言...”选择后重试。新建文档原先使用记住的语言时，会记住纠正后的选择；已保存文件或已在 Notepad++ 中指定受支持语言的文档，仅本次生效。依赖缺失、项目配置错误和超时不会触发语言重选，也不会自动尝试其他语言。

### 项目配置

对于已保存文档，桥接脚本读取 Prettier 配置并启用 EditorConfig 支持，同时从文件目录向上查找最近的 `.prettierignore`。

`.prettierrc` 示例：

```json
{
  "singleQuote": true,
  "semi": false,
  "tabWidth": 2
}
```

匹配忽略规则的文件会被跳过。默认沿用文档的 LF 或 CRLF 设置，项目配置可以覆盖该设置。JavaScript 编写的配置文件和额外的 Prettier 插件可能要求更新的 Node.js 版本或其他项目依赖。

## 常见问题

| 现象 | 检查方法 |
|---|---|
| 插件菜单中没有 NppFormatter | 确认 DLL 架构与 Notepad++ 一致，检查目录结构，并重启编辑器 |
| 点击格式化后打开 Settings | 首次使用前需要配置两项依赖路径 |
| Node.js 启动失败 | 使用 `process.execPath` 返回的实际 `node.exe` 绝对路径 |
| Prettier 加载失败 | 选择包含 `package.json` 的 Prettier 3.x 包目录，避免选成 `prettier.cmd` |
| 未保存文档出现语法错误 | 查看原始错误详情，修正代码或重新选择语言；整篇替换会清除记住的选择 |
| 已保存文件出现解析器或语法错误 | 检查扩展名、文件内容和项目配置；可使用“按指定语言格式化...”临时覆盖本次选择 |
| 文件被跳过，或结果被丢弃 | 检查 `.prettierignore`；停止编辑或切换文档后重新格式化 |
| 格式化超时 | 检查项目配置和插件，按需增大超时时间 |
| 提示需要 UTF-8 | 选择 **编码 → 转为 UTF-8 编码（Convert to UTF-8）**，然后重试 |
| 文档或选区不符合要求 | 缓冲区保持在 8 MiB 以内，使用单个普通光标或选区 |

格式化会替换整个缓冲区，书签和折叠位置可能移动；差量替换尚未实现。设置窗口的高 DPI 和读屏器表现仍需在正式发布前验证。

## 配置、升级与卸载

配置保存为 Notepad++ 提供的插件配置目录中的 `NppFormatter.ini`。保存已有配置时，会将上一个版本备份为 `NppFormatter.ini.bak`。关闭设置窗口后，将备份复制回 INI 即可恢复；下次格式化会重新读取。

升级时先关闭 Notepad++，备份 `plugins/NppFormatter`，再复制新文件夹。回退时关闭编辑器并恢复旧文件夹。卸载时在 Notepad++ 关闭状态下移除 `plugins/NppFormatter`；个人 INI 配置可保留供重新安装使用，也可单独删除。

## 从源码构建

构建工具：**LLVM-MinGW 20261104（UCRT）**、Node.js、npm、**Python 3.12+** 和 PowerShell。固定版本编译器运行于 Windows x64，或通过 x64 模拟运行于 Windows 11 ARM64，可交叉编译全部三种目标架构，替代原先仅使用 Zig 的构建方式。

在仓库根目录执行：

```powershell
npm ci
python scripts/bootstrap.py
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Architecture all
```

引导脚本下载固定版本编译器，并在解压前校验 SHA-256。已有 LLVM-MinGW 时，可通过 `-Toolchain` 参数或 `LLVM_MINGW_ROOT` 环境变量指定其根目录。`-Architecture` 接受 `x86`、`x64`（默认）、`arm64` 或 `all`。

构建脚本运行桥接测试，并在宿主可执行目标程序时运行原生进程测试。x64 Windows 会明确跳过 ARM64 运行测试；交叉编译成功不等于运行验证通过。`-SkipTests` 跳过桥接与原生测试，但始终校验安装包。每个 ZIP 均检查 PE 架构、六个 Notepad++ 导出函数、仅依赖系统 DLL，以及完整文件清单和内容。构建与暂存目录分别为 `build/<arch>` 和 `dist/<arch>/NppFormatter`，ZIP 与 SHA-256 校验文件输出到 `dist/`。

安装包仅包含 DLL、桥接脚本、中英文 README 和第三方许可说明；Node.js、Prettier、测试和构建工具不会打包。`npm ci` 安装的 Prettier 仅作为开发测试依赖。

| 命令 | 用途 |
|---|---|
| `npm test` | 使用真实 Prettier 验证格式化、配置、忽略规则、Unicode 光标偏移和错误返回 |
| `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1` | 构建 x64、运行桥接及原生测试并打包 |
| `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -Architecture all` | 构建并打包 x86、x64 和 ARM64 |
| `python -m unittest discover -s tests -p test_artifacts.py` | 构建后验证错误架构、缺失导出、多余文件和过期 ZIP 内容会被拒绝 |
| `python tests/editor_smoke.py --arch x64` | 在独立 Notepad++ 副本中测试指定架构 |

冒烟测试通过 `NPP_EXE`、`PATH` 或标准安装位置查找 Notepad++，启动前核对架构，在自动清理的临时目录中运行独立副本，检查格式化、光标映射、撤销、无变化时的行为和过期结果保护。测试结果摘要不记录本机路径。测试 x64/ARM64 编辑器时使用 64 位 Python。

CI 在 `windows-latest` 上构建 x86 和 x64，在 `windows-11-arm` 上构建 ARM64。各任务运行原生进程测试与对应架构的便携编辑器测试，通过后上传 ZIP 和校验文件。测试编辑器固定为 Notepad++ 8.9.6，下载后校验 SHA-256。配置工作流不代表测试已通过，请查看各架构实际运行结果；工作流不会自动发布 Release。

代码分为 `src/`（原生插件与进程管理）、`bridge/`（Prettier 集成）和 `tests/`。原型每次请求启动一个 Node.js 进程，同一时间只执行一个格式化请求。

编辑器测试默认覆盖英文、简体中文和繁体中文，可用 `--language en`、`--language zh-CN` 或 `--language zh-TW` 单独运行。便携测试编辑器需包含对应的官方语言 XML；`tests/download_npp.py` 会从校验过哈希的压缩包中提取这些文件。测试还会在配置输入尚未保存时，通过 Notepad++ 首选项切换语言。翻译集中维护于 `src/i18n.hpp`；CI 在每种 CPU 架构上运行全部三种语言的测试。

## 后续计划与参与

后续按以下阶段推进：

1. **通用执行与工具配置**：将进程管理与 Prettier 适配器分离，定义工具标识、语言映射、程序路径、参数数组、工作目录、超时及输入输出处理方式。
2. **接入多个适配器**：保留 Prettier 的配置查找和光标映射，再接入 clang-format 与 Ruff，验证通用执行模型。
3. **工具选择与诊断**：增加手动选择、按语言设置默认工具、项目级覆盖、依赖发现和可操作的环境检查。
4. **编辑器工作流**：增加选区格式化与保存时格式化，按工具能力启用，并沿用撤销和过期结果保护。
5. **文本转换与工具串联**：扩展压缩、转换和多个工具顺序执行；所有步骤成功后，才以一次可撤销操作写入最终结果。

进程复用、更多编码，以及书签和折叠位置的改善留待后续。目标架构与当前原型的验收条件见源码目录中的 `docs/SPEC.md`。

反馈问题时，请附上插件、Notepad++、Node.js 和 Prettier 版本，最小输入样例、相关配置、预期结果，以及完整的错误或状态消息。修改代码时运行相关测试，并同步维护两份 README。

---

第三方源码版本与许可说明记录在源码目录的 `third_party/README.md` 中；安装包在 `licenses/` 中附带许可文件。
