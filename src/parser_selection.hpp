#pragma once
#include <windows.h>
#include "Notepad_plus_msgs.h"
#include <iterator>
#include <string_view>

namespace formatter {
inline const char* parserForLanguage(int language) {
    switch (language) {
    case L_JAVASCRIPT: case L_JS_EMBEDDED: return "babel";
    case L_TYPESCRIPT: return "typescript";
    case L_JAVA: return "java";
    case L_PYTHON: return "python";
    case L_PHP: return "php";
    case L_SQL: return "sql";
    case L_PROPS: return "dot-properties";
    case L_TOML: return "toml";
    case L_BASH: return "sh";
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
    {L"PHP", "php"}, {L"SQL", "sql"}, {L"Properties", "dot-properties"},
    {L"TOML", "toml"}, {L"Shell / Bash", "sh"},
    {L"Python (Ruff)", "python"},
};

struct SqlDialect { const wchar_t* label; const wchar_t* value; };
inline constexpr SqlDialect sqlDialects[] = {
    {L"SQL", L"sql"}, {L"MySQL", L"mysql"}, {L"MariaDB", L"mariadb"},
    {L"PostgreSQL", L"postgresql"}, {L"SQLite", L"sqlite"},
    {L"SQL Server (T-SQL)", L"transactsql"}, {L"Oracle (PL/SQL)", L"plsql"},
    {L"BigQuery", L"bigquery"}, {L"Snowflake", L"snowflake"},
    {L"IBM Db2", L"db2"}, {L"IBM Db2 for i", L"db2i"}, {L"Hive", L"hive"},
    {L"Couchbase N1QL", L"n1ql"}, {L"Redshift", L"redshift"},
    {L"SingleStoreDB", L"singlestoredb"}, {L"Spark", L"spark"},
    {L"Trino", L"trino"}, {L"ClickHouse", L"clickhouse"},
};
inline size_t sqlDialectIndex(std::wstring_view value) {
    for (size_t i = 0; i < std::size(sqlDialects); ++i)
        if (value == sqlDialects[i].value) return i;
    return 0;
}
struct ShellDialect { const wchar_t* label; int value; };
inline constexpr ShellDialect shellDialects[] = {
    {L"Bash", 1}, {L"POSIX sh", 2}, {L"mksh", 4}, {L"Bats", 8},
};
inline size_t shellDialectIndex(int value) {
    for (size_t i = 0; i < std::size(shellDialects); ++i)
        if (value == shellDialects[i].value) return i;
    return 0;
}
} // namespace formatter
