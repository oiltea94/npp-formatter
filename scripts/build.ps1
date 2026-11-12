param([string]$Zig = '', [switch]$SkipTests)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    if (-not $Zig) { $Zig = $env:ZIG_EXE }
    if (-not $Zig) {
        $zigCommand = Get-Command zig -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($zigCommand) { $Zig = $zigCommand.Source }
    }
    if (-not $Zig -or -not (Test-Path -LiteralPath $Zig -PathType Leaf)) {
        throw 'Install Zig 0.14.1 on PATH, set ZIG_EXE, or pass -Zig with its executable path.'
    }
    $Zig = (Resolve-Path -LiteralPath $Zig).Path
    New-Item -ItemType Directory -Force -Path 'build','dist\NppFormatter\licenses' | Out-Null
    $flags = @('-target','x86_64-windows-gnu','-std=c++17','-O2','-DUNICODE','-D_UNICODE','-DNOMINMAX','-Wall','-Wextra','-Isrc','-Ithird_party/npp','-Ithird_party/json')
    & $Zig c++ @flags -shared -static 'src/plugin.cpp' -o 'build/NppFormatter.dll' -lcomdlg32 -luser32 -lgdi32
    if ($LASTEXITCODE -ne 0) { throw 'Plugin build failed.' }
    & $Zig c++ @flags -municode 'tests/process_test.cpp' -o 'build/process_test.exe'
    if ($LASTEXITCODE -ne 0) { throw 'Process test build failed.' }
    if (-not $SkipTests) {
        & npm test
        if ($LASTEXITCODE -ne 0) { throw 'Bridge tests failed.' }
        $nodePath = & node -p 'process.execPath'
        & '.\build\process_test.exe' $nodePath (Join-Path $root 'tests\process-fixture.cjs')
        if ($LASTEXITCODE -ne 0) { throw 'Native process tests failed.' }
    }
    Copy-Item -LiteralPath 'build\NppFormatter.dll' -Destination 'dist\NppFormatter\NppFormatter.dll'
    Copy-Item -LiteralPath 'bridge\bridge.cjs' -Destination 'dist\NppFormatter\bridge.cjs'
    Copy-Item -LiteralPath 'README.md' -Destination 'dist\NppFormatter\README.md'
    Copy-Item -LiteralPath 'README.zh-CN.md' -Destination 'dist\NppFormatter\README.zh-CN.md'
    Copy-Item -LiteralPath 'third_party\npp\LICENSE' -Destination 'dist\NppFormatter\licenses\NotepadPlusPlus-GPL.txt'
    Copy-Item -LiteralPath 'third_party\npp\Scintilla-LICENSE.txt' -Destination 'dist\NppFormatter\licenses\Scintilla.txt'
    Copy-Item -LiteralPath 'third_party\json\LICENSE.MIT' -Destination 'dist\NppFormatter\licenses\nlohmann-json.txt'
    $allowed = @('NppFormatter.dll', 'bridge.cjs', 'README.md', 'README.zh-CN.md', 'licenses/NotepadPlusPlus-GPL.txt', 'licenses/Scintilla.txt', 'licenses/nlohmann-json.txt')
    Add-Type -AssemblyName System.IO.Compression
    $archivePath = Join-Path $root 'dist\NppFormatter-0.1.0-x64.zip'
    $stream = [System.IO.File]::Open($archivePath, [System.IO.FileMode]::Create)
    $archive = New-Object System.IO.Compression.ZipArchive($stream, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($name in $allowed) {
            $entry = $archive.CreateEntry("NppFormatter/$name")
            $output = $entry.Open()
            $inputFile = [System.IO.File]::OpenRead((Join-Path "$root\dist\NppFormatter" $name))
            try { $inputFile.CopyTo($output) } finally { $inputFile.Dispose(); $output.Dispose() }
        }
    } finally { $archive.Dispose(); $stream.Dispose() }
    [PSCustomObject]@{
        Package = 'dist/NppFormatter-0.1.0-x64.zip'
        SHA256 = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash
    }
} finally { Pop-Location }
