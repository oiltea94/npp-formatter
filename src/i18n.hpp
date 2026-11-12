#pragma once
#include <algorithm>
#include <cctype>
#include <string>

namespace formatter::i18n {
enum class Language { English, SimplifiedChinese, TraditionalChinese };

inline Language fromNativeFileName(std::string filename) {
    auto slash = filename.find_last_of("/\\");
    if (slash != std::string::npos) filename.erase(0, slash + 1);
    std::transform(filename.begin(), filename.end(), filename.begin(),
                   [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    if (filename == "chinesesimplified.xml") return Language::SimplifiedChinese;
    if (filename == "taiwanesemandarin.xml" || filename == "hongkongcantonese.xml")
        return Language::TraditionalChinese;
    return Language::English;
}

enum class Text {
    Empty, Format, Settings, About, SettingsTitle, AboutTitle, ErrorTitle,
    NodeLabel, PrettierLabel, TimeoutLabel, Browse, Detect, Save, Cancel,
    NodeFilter, PrettierFilter, NodeFirst, DetectNode, DetectPrettier, Detected,
    DetectionFailed, DetectionTimerError, TimeoutError, NodePathError, PrettierPathError,
    CreateSettingsError, WriteSettingsError, ReplaceSettingsError, AboutBody,
    ProjectHomepage, OpenHomepageError, AboutDialogError,
    ParserTitle, ParserPrompt, ParserDialogError, ChooseLanguage, FormatCancelled,
    FormatAs, ParserOncePrompt, ParseErrorTitle, ParseErrorPrompt, ErrorDetails, ChooseAgain,
    Busy, Formatting, Discarded, Ignored, Unchanged, Formatted, FormatFailed, Count
};

struct Translation { const wchar_t* english; const wchar_t* simplified; const wchar_t* traditional; };
inline constexpr Translation translations[] = {
    {L"", L"", L""},
    {L"Format document", L"格式化文档", L"格式化文件"},
    {L"Settings...", L"配置...", L"設定..."},
    {L"About", L"关于", L"關於"},
    {L"NppFormatter settings", L"NppFormatter 配置", L"NppFormatter 設定"},
    {L"About NppFormatter", L"关于 NppFormatter", L"關於 NppFormatter"},
    {L"NppFormatter error", L"NppFormatter 错误", L"NppFormatter 錯誤"},
    {L"Node.js executable (node.exe)", L"Node.js 可执行文件（node.exe）", L"Node.js 執行檔（node.exe）"},
    {L"Prettier 3.x package directory (browse to its package.json)", L"Prettier 3.x 包目录（浏览时选择 package.json）", L"Prettier 3.x 套件目錄（瀏覽時選擇 package.json）"},
    {L"Timeout in milliseconds (1000 - 120000)", L"超时时间，毫秒（1000 - 120000）", L"逾時時間，毫秒（1000 - 120000）"},
    {L"Browse...", L"浏览...", L"瀏覽..."},
    {L"Auto-detect", L"自动检测", L"自動偵測"},
    {L"Save", L"保存", L"儲存"},
    {L"Cancel", L"取消", L"取消"},
    {L"Node executable\0*.exe\0\0", L"Node 可执行文件\0*.exe\0\0", L"Node 執行檔\0*.exe\0\0"},
    {L"Prettier package.json\0package.json\0\0", L"Prettier 包文件\0package.json\0\0", L"Prettier 套件檔案\0package.json\0\0"},
    {L"Detect or browse for Node.js first, then detect Prettier.", L"请先检测或浏览选择 Node.js，再检测 Prettier。", L"請先偵測或瀏覽選擇 Node.js，再偵測 Prettier。"},
    {L"Detecting Node.js...", L"正在检测 Node.js...", L"正在偵測 Node.js..."},
    {L"Detecting Prettier...", L"正在检测 Prettier...", L"正在偵測 Prettier..."},
    {L"Detected. Click Save to keep the paths.", L"检测成功，点击“保存”以保留路径。", L"偵測成功，點擊「儲存」以保留路徑。"},
    {L"Detection failed. Check the installation or use Browse.", L"检测失败，请检查安装情况或使用“浏览”选择路径。", L"偵測失敗，請檢查安裝情況或使用「瀏覽」選擇路徑。"},
    {L"Could not start detection timer.", L"启动自动检测失败。", L"啟動自動偵測失敗。"},
    {L"Timeout must be between 1000 and 120000 milliseconds.", L"超时时间必须为 1000 至 120000 毫秒。", L"逾時時間必須為 1000 至 120000 毫秒。"},
    {L"Select an existing absolute node.exe path.", L"请选择已存在的 node.exe 文件的绝对路径。", L"請選擇已存在的 node.exe 檔案的絕對路徑。"},
    {L"Select the Prettier package directory containing package.json.", L"请选择包含 package.json 的 Prettier 包目录。", L"請選擇包含 package.json 的 Prettier 套件目錄。"},
    {L"Could not create the settings file.", L"创建配置文件失败。", L"建立設定檔失敗。"},
    {L"Could not write settings.", L"写入配置失败。", L"寫入設定失敗。"},
    {L"Could not replace settings file.", L"替换配置文件失败。", L"取代設定檔失敗。"},
    {L"NppFormatter 0.1.0 prototype\n\nRequires user-installed Node.js 18+ and Prettier 3.x.\nConfigure both paths in Settings. UTF-8 buffers, full-document formatting.\n\nFormatting languages (13 picker choices):\nJavaScript / JSX, TypeScript / TSX, JSON, JSON5, HTML, CSS, SCSS, Less, YAML, Markdown, GraphQL, Vue, Angular HTML.\n\nAdditional saved-file formats: Flow, JSONC, MDX, Handlebars, MJML, PostCSS, JSON.stringify.\n\nAssign shortcuts through Notepad++ Shortcut Mapper.\nNode.js, Prettier and language plugins are not bundled.",
     L"NppFormatter 0.1.0 原型版本\n\n需要自行安装 Node.js 18+ 和 Prettier 3.x。\n请在配置中选择或自动检测路径。支持 UTF-8 文档的全文格式化。\n\n格式化语言（选择器提供 13 项）：\nJavaScript / JSX、TypeScript / TSX、JSON、JSON5、HTML、CSS、SCSS、Less、YAML、Markdown、GraphQL、Vue、Angular HTML。\n\n已保存文件另支持：Flow、JSONC、MDX、Handlebars、MJML、PostCSS、JSON.stringify。\n\n可通过 Notepad++ 的快捷键管理设置快捷键。\n插件不捆绑 Node.js、Prettier 或语言扩展包。",
     L"NppFormatter 0.1.0 原型版本\n\n需要自行安裝 Node.js 18+ 和 Prettier 3.x。\n請在設定中選擇或自動偵測路徑。支援 UTF-8 文件的全文格式化。\n\n格式化語言（選擇器提供 13 項）：\nJavaScript / JSX、TypeScript / TSX、JSON、JSON5、HTML、CSS、SCSS、Less、YAML、Markdown、GraphQL、Vue、Angular HTML。\n\n已儲存檔案另支援：Flow、JSONC、MDX、Handlebars、MJML、PostCSS、JSON.stringify。\n\n可透過 Notepad++ 的快捷鍵管理設定快捷鍵。\n外掛不附帶 Node.js、Prettier 或語言擴充套件。"},
    {L"Project homepage:", L"项目主页：", L"專案首頁："},
    {L"Could not open the project homepage. Copy this address into your browser:\nhttps://github.com/oiltea94/npp-formatter",
     L"打开项目主页失败。请将此地址复制到浏览器：\nhttps://github.com/oiltea94/npp-formatter",
     L"開啟專案首頁失敗。請將此網址複製到瀏覽器：\nhttps://github.com/oiltea94/npp-formatter"},
    {L"Could not open the About dialog.", L"打开关于窗口失败。", L"開啟關於視窗失敗。"},
    {L"Choose document language", L"选择文档语言", L"選擇文件語言"},
    {L"Choose a language for this document. Remembered until all text is replaced, the document is closed/saved, or its language changes.",
     L"请选择此文档的语言。选择仅用于当前文档，整篇替换、关闭、保存或切换文档语言后清除。",
     L"請選擇此文件的語言。選擇僅用於目前文件，整篇取代、關閉、儲存或切換文件語言後清除。"},
    {L"Could not open the language picker.", L"打开语言选择窗口失败。", L"開啟語言選擇視窗失敗。"},
    {L"NppFormatter: choose this document's language", L"NppFormatter：请选择当前文档的语言", L"NppFormatter：請選擇目前文件的語言"},
    {L"NppFormatter: formatting cancelled", L"NppFormatter：已取消格式化", L"NppFormatter：已取消格式化"},
    {L"Format with language...", L"按指定语言格式化...", L"依指定語言格式化..."},
    {L"Choose a language for this formatting operation only. The file type and remembered document language stay unchanged.",
     L"请选择本次格式化使用的语言。仅本次生效，不改变文件类型或文档记住的语言。",
     L"請選擇本次格式化使用的語言。僅本次生效，不變更檔案類型或文件記住的語言。"},
    {L"Formatting could not parse this document", L"格式化时未能解析文档", L"格式化時未能解析文件"},
    {L"There may be a syntax error or a language mismatch. Review the original error details, or choose another language and retry. Your text has not been changed.",
     L"可能存在语法错误，或所选语言与内容不匹配。请查看原始错误详情，或重新选择语言后重试。文档内容未修改。",
     L"可能存在語法錯誤，或所選語言與內容不符。請查看原始錯誤詳情，或重新選擇語言後重試。文件內容未修改。"},
    {L"Show error details", L"查看错误详情", L"查看錯誤詳情"},
    {L"Choose another language...", L"重新选择语言...", L"重新選擇語言..."},
    {L"NppFormatter: formatting already in progress", L"NppFormatter：正在格式化，请稍候", L"NppFormatter：正在格式化，請稍候"},
    {L"NppFormatter: formatting...", L"NppFormatter：正在格式化...", L"NppFormatter：正在格式化..."},
    {L"NppFormatter: document changed; result discarded", L"NppFormatter：文档已变化，已丢弃结果", L"NppFormatter：文件已變更，已捨棄結果"},
    {L"NppFormatter: skipped by .prettierignore", L"NppFormatter：已按 .prettierignore 跳过", L"NppFormatter：已依 .prettierignore 略過"},
    {L"NppFormatter: already formatted", L"NppFormatter：无需格式化", L"NppFormatter：無需格式化"},
    {L"NppFormatter: formatted (Ctrl+Z to undo)", L"NppFormatter：格式化完成（Ctrl+Z 撤销）", L"NppFormatter：格式化完成（Ctrl+Z 復原）"},
    {L"NppFormatter: formatting failed", L"NppFormatter：格式化失败", L"NppFormatter：格式化失敗"},
};
static_assert(sizeof(translations) / sizeof(translations[0]) == static_cast<size_t>(Text::Count));

inline const wchar_t* get(Text key, Language language) {
    const auto& value = translations[static_cast<size_t>(key)];
    switch (language) {
    case Language::SimplifiedChinese: return value.simplified;
    case Language::TraditionalChinese: return value.traditional;
    default: return value.english;
    }
}
} // namespace formatter::i18n
