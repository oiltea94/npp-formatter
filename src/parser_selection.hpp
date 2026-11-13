#pragma once
#include <windows.h>
#include "Notepad_plus_msgs.h"

namespace formatter {
inline const char* parserForLanguage(int language) {
    switch (language) {
    case L_JAVASCRIPT: case L_JS_EMBEDDED: return "babel";
    case L_TYPESCRIPT: return "typescript";
    case L_JAVA: return "java";
    case L_JSON: return "json";
    case L_JSON5: return "json5";
    case L_HTML: return "html";
    case L_XML: return "xml";
    case L_CSS: return "css";
    case L_YAML: return "yaml";
    default: return nullptr;
    }
}

struct ParserChoice { const wchar_t* label; const char* parser; };
inline constexpr ParserChoice parserChoices[] = {
    {L"JavaScript / JSX", "babel"}, {L"TypeScript / TSX", "typescript"},
    {L"JSON", "json"}, {L"JSON5", "json5"}, {L"HTML", "html"},
    {L"CSS", "css"}, {L"SCSS", "scss"}, {L"Less", "less"},
    {L"YAML", "yaml"}, {L"Markdown", "markdown"}, {L"GraphQL", "graphql"},
    {L"Vue", "vue"}, {L"Angular HTML", "angular"},
    {L"Java", "java"},
    {L"XML", "xml"}, {L"JSONC", "jsonc"}, {L"MDX", "mdx"}, {L"Handlebars", "glimmer"},
};
} // namespace formatter
