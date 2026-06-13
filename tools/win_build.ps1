[CmdletBinding()]
param(
    [ValidateSet('build','clean','info')]
    [string]$Action = 'build',

    [ValidateSet('release','debug')]
    [string]$BuildType = 'release'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Repo = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$BuildDir = Join-Path $Repo 'build'
$ThirdParty = Join-Path $Repo 'third_party'

# Single source of truth: parse SDL2_VERSION out of build.mk. Falls back to a
# safe default if build.mk goes missing, but emits a warning so drift is visible.
$BuildMk = Join-Path $Repo 'build.mk'
$Sdl2Version = '2.30.9'
if (Test-Path $BuildMk) {
    $line = Select-String -Path $BuildMk -Pattern '^\s*SDL2_VERSION\s*=\s*(\S+)' -List
    if ($line) { $Sdl2Version = $line.Matches[0].Groups[1].Value }
    else { Write-Warning "SDL2_VERSION not found in $BuildMk - using fallback $Sdl2Version" }
} else {
    Write-Warning "build.mk not found at $BuildMk - using fallback SDL2 version $Sdl2Version"
}
$Sdl2RootName = "SDL2-$Sdl2Version"
$Sdl2Url = "https://github.com/libsdl-org/SDL/releases/download/release-$Sdl2Version/SDL2-devel-$Sdl2Version-VC.zip"
$cmakeBuildType = if ($BuildType -eq 'debug') { 'Debug' } else { 'Release' }

function Find-VsInstall {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path $vswhere)) {
        throw "vswhere.exe not found at $vswhere. Visual Studio 2022 (with Native Desktop workload) is required."
    }
    $path = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Workload.NativeDesktop -property installationPath
    if (-not $path) {
        throw "Visual Studio with the 'Desktop development with C++' workload was not found. Install it via the VS Installer."
    }
    return $path.Trim()
}

function Resolve-MsvcToolsVersion {
    param([string]$VsPath)
    $msvcRoot = Join-Path $VsPath 'VC\Tools\MSVC'
    if (-not (Test-Path $msvcRoot)) { return $null }
    $latest = Get-ChildItem -Directory $msvcRoot | Sort-Object Name -Descending | Select-Object -First 1
    if ($latest) { return $latest.Name } else { return $null }
}

function Resolve-BundledTools {
    param([string]$VsPath)
    $cmake = Join-Path $VsPath 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
    $ninja = Join-Path $VsPath 'Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe'
    $vcvars = Join-Path $VsPath 'VC\Auxiliary\Build\vcvars64.bat'
    foreach ($pair in @(@{n='cmake.exe';p=$cmake}, @{n='ninja.exe';p=$ninja}, @{n='vcvars64.bat';p=$vcvars})) {
        if (-not (Test-Path $pair.p)) {
            throw "Bundled $($pair.n) not found at $($pair.p). The Visual Studio C++ workload may be incomplete."
        }
    }
    return [pscustomobject]@{ CMake = $cmake; Ninja = $ninja; Vcvars = $vcvars }
}

function Get-Sdl2VersionFromHeader {
    param([string]$Sdl2Root)
    $hdr = Join-Path $Sdl2Root 'include\SDL_version.h'
    if (-not (Test-Path $hdr)) { return $null }
    $text = Get-Content $hdr -Raw
    $maj = [regex]::Match($text, '#define\s+SDL_MAJOR_VERSION\s+(\d+)').Groups[1].Value
    $min = [regex]::Match($text, '#define\s+SDL_MINOR_VERSION\s+(\d+)').Groups[1].Value
    $pat = [regex]::Match($text, '#define\s+SDL_PATCHLEVEL\s+(\d+)').Groups[1].Value
    if ($maj -and $min -and $pat) { return "$maj.$min.$pat" }
    return $null
}

function Resolve-Sdl2Path {
    # Returns @{Root=...; CMakeDir=...; Source='env'|'cached'|'absent'} or $null with Source='absent'
    if ($env:SDL2_DIR -and (Test-Path $env:SDL2_DIR)) {
        $root = $env:SDL2_DIR
        # If SDL2_DIR points at the cmake subdir, climb up
        if ((Split-Path -Leaf $root) -ieq 'cmake') {
            $maybeRoot = Split-Path -Parent $root
            if (Test-Path (Join-Path $maybeRoot 'include\SDL_version.h')) { $root = $maybeRoot }
        }
        $cmakeDir = Join-Path $root 'cmake'
        return [pscustomobject]@{ Root = $root; CMakeDir = $cmakeDir; Source = 'env' }
    }
    $cachedRoot = Join-Path $ThirdParty $Sdl2RootName
    $cachedCmake = Join-Path $cachedRoot 'cmake'
    if (Test-Path (Join-Path $cachedCmake 'sdl2-config.cmake')) {
        return [pscustomobject]@{ Root = $cachedRoot; CMakeDir = $cachedCmake; Source = 'cached' }
    }
    return [pscustomobject]@{ Root = $cachedRoot; CMakeDir = $cachedCmake; Source = 'absent' }
}

function Ensure-Sdl2 {
    $resolved = Resolve-Sdl2Path
    if ($resolved.Source -ne 'absent') { return $resolved }

    Write-Host "==> Fetching SDL2 $Sdl2Version dev libs..."
    if (-not (Test-Path $ThirdParty)) {
        New-Item -ItemType Directory -Path $ThirdParty | Out-Null
    }
    $zipPath = Join-Path $ThirdParty "SDL2-devel-$Sdl2Version-VC.zip"
    if (-not (Test-Path $zipPath)) {
        Write-Host "    Downloading $Sdl2Url"
        $oldProgress = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        try {
            Invoke-WebRequest -Uri $Sdl2Url -OutFile $zipPath -UseBasicParsing
        } finally {
            $ProgressPreference = $oldProgress
        }
    }
    Write-Host "    Extracting to $ThirdParty"
    Expand-Archive -Path $zipPath -DestinationPath $ThirdParty -Force

    $resolved = Resolve-Sdl2Path
    if ($resolved.Source -eq 'absent' -or -not (Test-Path (Join-Path $resolved.CMakeDir 'sdl2-config.cmake'))) {
        throw "SDL2 extraction did not yield $($resolved.CMakeDir)\sdl2-config.cmake. Please inspect $ThirdParty."
    }
    return $resolved
}

function Import-VcvarsEnv {
    param([string]$Vcvars)
    Write-Host "==> Importing MSVC environment (vcvars64)"
    $cmd = "`"$Vcvars`" >NUL && set"
    $lines = & cmd.exe /c $cmd
    if ($LASTEXITCODE -ne 0) {
        throw "vcvars64.bat failed with exit code $LASTEXITCODE"
    }
    foreach ($line in $lines) {
        if ($line -match '^([^=]+)=(.*)$') {
            $name = $matches[1]
            $value = $matches[2]
            Set-Item -Path "Env:$name" -Value $value -ErrorAction SilentlyContinue
        }
    }
}

function Find-BuiltExe {
    $candidates = @(
        (Join-Path $BuildDir 'duke3d.exe'),
        (Join-Path $BuildDir "$cmakeBuildType\duke3d.exe")
    )
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    return $null
}

function Do-Info {
    Write-Host "=== Duke3D Windows Build Configuration ==="

    try {
        $vs = Find-VsInstall
        Write-Host "VS:        $vs"
    } catch {
        Write-Host "VS:        (not found: $($_.Exception.Message))"
        $vs = $null
    }

    if ($vs) {
        $msvc = Resolve-MsvcToolsVersion -VsPath $vs
        if ($msvc) { Write-Host "MSVC:      $msvc" } else { Write-Host "MSVC:      (not found)" }

        $cmakeExe = Join-Path $vs 'Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin\cmake.exe'
        if (Test-Path $cmakeExe) {
            $cmakeVer = (& $cmakeExe --version | Select-Object -First 1) -replace '^cmake version\s+',''
            Write-Host "CMake:     $cmakeVer"
        } else {
            Write-Host "CMake:     (not bundled)"
        }

        $ninjaExe = Join-Path $vs 'Common7\IDE\CommonExtensions\Microsoft\CMake\Ninja\ninja.exe'
        if (Test-Path $ninjaExe) {
            $ninjaVer = (& $ninjaExe --version | Select-Object -First 1).Trim()
            Write-Host "Ninja:     $ninjaVer"
        } else {
            Write-Host "Ninja:     (not bundled)"
        }
    } else {
        Write-Host "MSVC:      (n/a)"
        Write-Host "CMake:     (n/a)"
        Write-Host "Ninja:     (n/a)"
    }

    $sdl2 = Resolve-Sdl2Path
    if ($sdl2.Source -eq 'absent') {
        Write-Host "SDL2:      not present (will auto-fetch on build)"
    } else {
        $ver = Get-Sdl2VersionFromHeader -Sdl2Root $sdl2.Root
        if (-not $ver) {
            $leaf = Split-Path -Leaf $sdl2.Root
            if ($leaf -match 'SDL2-(\d+\.\d+\.\d+)') { $ver = $matches[1] } else { $ver = 'unknown' }
        }
        $tag = if ($sdl2.Source -eq 'env') { 'from $env:SDL2_DIR' } else { 'auto-fetched' }
        Write-Host "SDL2:      $($sdl2.Root) ($tag, v$ver)"
    }

    $exe = Join-Path $Repo 'duke3d.exe'
    if (Test-Path $exe) {
        Write-Host "duke3d.exe: present"
    } else {
        Write-Host "duke3d.exe: not built"
    }
    Write-Host "=========================================="
}

function Do-Clean {
    Write-Host "==> Cleaning build artifacts"
    foreach ($p in @($BuildDir, (Join-Path $Repo 'duke3d.exe'), (Join-Path $Repo 'SDL2.dll'))) {
        if (Test-Path $p) {
            Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "    removed $p"
        }
    }
    Write-Host "Clean complete."
}

function Do-Build {
    $vs = Find-VsInstall
    Write-Host "==> Visual Studio: $vs"
    $tools = Resolve-BundledTools -VsPath $vs

    $sdl2 = Ensure-Sdl2
    Write-Host "==> SDL2: $($sdl2.Root)"

    Import-VcvarsEnv -Vcvars $tools.Vcvars

    if (-not (Test-Path $BuildDir)) {
        New-Item -ItemType Directory -Path $BuildDir | Out-Null
    }

    $marker = Join-Path $BuildDir '.win_build_type'
    $cacheFile = Join-Path $BuildDir 'CMakeCache.txt'
    $needConfigure = $true
    if ((Test-Path $cacheFile) -and (Test-Path $marker)) {
        $existing = (Get-Content $marker -Raw).Trim()
        if ($existing -eq $cmakeBuildType) { $needConfigure = $false }
    }

    if ($needConfigure) {
        Write-Host "==> Configuring ($cmakeBuildType)"
        & $tools.CMake -S $Repo -B $BuildDir -G Ninja `
            "-DCMAKE_BUILD_TYPE=$cmakeBuildType" `
            "-DCMAKE_C_COMPILER=cl" `
            "-DCMAKE_MAKE_PROGRAM=$($tools.Ninja)" `
            "-DSDL2_DIR=$($sdl2.CMakeDir)"
        if ($LASTEXITCODE -ne 0) { throw "CMake configure failed (exit $LASTEXITCODE)" }
        Set-Content -Path $marker -Value $cmakeBuildType -NoNewline
    } else {
        Write-Host "==> Configuration up-to-date ($cmakeBuildType); skipping configure"
    }

    Write-Host "==> Building"
    & $tools.CMake --build $BuildDir --config $cmakeBuildType -j
    if ($LASTEXITCODE -ne 0) { throw "Build failed (exit $LASTEXITCODE)" }

    Write-Host "==> Copying outputs"
    $exe = Find-BuiltExe
    if (-not $exe) {
        throw "Could not locate built duke3d.exe under $BuildDir."
    }
    $exeDest = Join-Path $Repo 'duke3d.exe'
    Copy-Item -Path $exe -Destination $exeDest -Force
    Write-Host "    $exe -> $exeDest"

    $dllSrc = Join-Path $sdl2.Root 'lib\x64\SDL2.dll'
    if (-not (Test-Path $dllSrc)) {
        throw "SDL2.dll not found at $dllSrc"
    }
    $dllDest = Join-Path $Repo 'SDL2.dll'
    Copy-Item -Path $dllSrc -Destination $dllDest -Force
    Write-Host "    $dllSrc -> $dllDest"

    Write-Host "Build complete: duke3d.exe ($BuildType)"
}

switch ($Action) {
    'info'  { Do-Info }
    'clean' { Do-Clean }
    'build' { Do-Build }
}
