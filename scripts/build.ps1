param(
    [ValidateSet('x86', 'x64', 'arm64', 'all')][string]$Architecture = 'x64',
    [string]$Toolchain = '',
    [switch]$SkipTests,
    [switch]$RequireRuntimeTests
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    if ($SkipTests -and $RequireRuntimeTests) { throw '-SkipTests conflicts with -RequireRuntimeTests.' }
    if (-not $Toolchain) { $Toolchain = $env:LLVM_MINGW_ROOT }
    if (-not $Toolchain) { $Toolchain = Join-Path $root '.tools\llvm-mingw-20261104-ucrt-x86_64' }
    $targets = @{ x86 = 'i686'; x64 = 'x86_64'; arm64 = 'aarch64' }
    $architectures = if ($Architecture -eq 'all') { @('x86', 'x64', 'arm64') } else { @($Architecture) }
    $version = (Get-Content -LiteralPath 'package.json' -Raw | ConvertFrom-Json).version
    $hostArchitecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
    if (-not $SkipTests) {
        & npm test
        if ($LASTEXITCODE -ne 0) { throw 'Bridge tests failed. Run npm ci before building.' }
        $nodePath = & node -p 'process.execPath'
        if ($LASTEXITCODE -ne 0) { throw 'Node.js executable lookup failed.' }
    }
    Add-Type -AssemblyName System.IO.Compression
    foreach ($arch in $architectures) {
        $compiler = Join-Path $Toolchain "bin\$($targets[$arch])-w64-mingw32-clang++.exe"
        if (-not (Test-Path -LiteralPath $compiler -PathType Leaf)) {
            throw 'LLVM-MinGW missing. Run python scripts/bootstrap.py or set LLVM_MINGW_ROOT / -Toolchain.'
        }
        $build = "build/$arch"
        $stage = "dist/$arch/NppFormatter"
        New-Item -ItemType Directory -Force -Path $build,"$stage/licenses" | Out-Null
        & python 'scripts/release.py' prepare --build-dir $build
        if ($LASTEXITCODE -ne 0) { throw 'Version resource generation failed.' }
        $resourceCompiler = Join-Path $Toolchain "bin\$($targets[$arch])-w64-mingw32-windres.exe"
        & $resourceCompiler "$build/version.rc" -O coff -o "$build/version.o"
        if ($LASTEXITCODE -ne 0) { throw "$arch version resource compilation failed." }
        $flags = @('-std=c++17', '-O2', '-static', '-DUNICODE', '-D_UNICODE', '-DNOMINMAX',
                   '-Wall', '-Wextra', '-Isrc', "-I$build", '-Ithird_party/npp', '-Ithird_party/json')
        & $compiler @flags -shared 'src/plugin.cpp' "$build/version.o" -o "$build/NppFormatter.dll" -lcomdlg32 -lcomctl32 -lshell32 -luser32 -lgdi32
        if ($LASTEXITCODE -ne 0) { throw "$arch plugin build failed." }
        & $compiler @flags -municode 'tests/process_test.cpp' -o "$build/process_test.exe"
        if ($LASTEXITCODE -ne 0) { throw "$arch process test build failed." }
        & $compiler @flags -municode 'tests/ui_automation.cpp' -o "$build/ui_automation.exe" -lole32 -loleaut32 -luuid
        if ($LASTEXITCODE -ne 0) { throw "$arch UI Automation helper build failed." }
        $canRun = ($arch -eq 'x86') -or ($arch -eq 'x64' -and $hostArchitecture -eq 'AMD64') -or ($arch -eq 'arm64' -and $hostArchitecture -eq 'ARM64')
        if ($RequireRuntimeTests -and -not $canRun) { throw "$arch runtime tests require a matching Windows host." }
        if (-not $SkipTests -and $canRun) {
            & "./$build/process_test.exe" $nodePath (Join-Path $root 'tests/process-fixture.cjs')
            if ($LASTEXITCODE -ne 0) { throw "$arch native process tests failed." }
        } else {
            Write-Host "SKIP $arch runtime tests (host=$hostArchitecture, SkipTests=$SkipTests); static package verification still runs."
        }
        Copy-Item -LiteralPath "$build/NppFormatter.dll" -Destination "$stage/NppFormatter.dll"
        Copy-Item -LiteralPath 'bridge/bridge.cjs','README.md','README.zh-CN.md' -Destination $stage
        Copy-Item -LiteralPath 'third_party/npp/LICENSE' -Destination "$stage/licenses/NotepadPlusPlus-GPL.txt"
        Copy-Item -LiteralPath 'third_party/npp/Scintilla-LICENSE.txt' -Destination "$stage/licenses/Scintilla.txt"
        Copy-Item -LiteralPath 'third_party/json/LICENSE.MIT' -Destination "$stage/licenses/nlohmann-json.txt"
        $allowed = @('NppFormatter.dll', 'bridge.cjs', 'README.md', 'README.zh-CN.md', 'licenses/NotepadPlusPlus-GPL.txt', 'licenses/Scintilla.txt', 'licenses/nlohmann-json.txt')
        $archivePath = "dist/NppFormatter-$version-$arch.zip"
        $stream = [System.IO.File]::Open((Join-Path $root $archivePath), [System.IO.FileMode]::Create)
        $archive = New-Object System.IO.Compression.ZipArchive($stream, [System.IO.Compression.ZipArchiveMode]::Create)
        try {
            foreach ($name in $allowed) {
                $entry = $archive.CreateEntry("NppFormatter/$name")
                $output = $entry.Open()
                $inputFile = [System.IO.File]::OpenRead((Join-Path "$root/$stage" $name))
                try { $inputFile.CopyTo($output) } finally { $inputFile.Dispose(); $output.Dispose() }
            }
        } finally { $archive.Dispose(); $stream.Dispose() }
        & python 'scripts/verify_package.py' --arch $arch --package $archivePath --stage $stage
        if ($LASTEXITCODE -ne 0) { throw "$arch package verification failed." }
        $hash = (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $([System.IO.Path]::GetFileName($archivePath))" | Set-Content -LiteralPath "$archivePath.sha256" -Encoding ascii
        [PSCustomObject]@{ Package = $archivePath; SHA256 = $hash }
    }
} finally { Pop-Location }
