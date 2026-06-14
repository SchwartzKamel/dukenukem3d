[CmdletBinding()]
param(
    [switch]$Fast,
    [switch]$BuildOnly,
    [switch]$SkipRequirementsInstall
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ToolDir = Split-Path -Parent $PSCommandPath
$EngineRoot = Split-Path -Parent $ToolDir
$RepoRoot = Split-Path -Parent $EngineRoot
$WinBuild = Join-Path $ToolDir 'win_build.ps1'
$Requirements = Join-Path $EngineRoot 'requirements.txt'
$GenerateAssets = Join-Path $ToolDir 'generate_assets.py'
$AllocacheTest = Join-Path $EngineRoot 'tests\test_allocache.py'
$VisualPlaytest = Join-Path $EngineRoot 'tests\test_visual_playtest.py'
$CapturesDir = Join-Path $EngineRoot 'captures'
$StartupLog = Join-Path $EngineRoot 'atomic_shell_startup.log'
$BuiltExeCandidates = @(
    (Join-Path $EngineRoot 'build\Release\duke3d.exe'),
    (Join-Path $EngineRoot 'build\duke3d.exe')
)
$BuiltExe = $BuiltExeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
$EngineExe = Join-Path $EngineRoot 'duke3d.exe'
$EngineDll = Join-Path $EngineRoot 'SDL2.dll'
$GeneratedGrp = Join-Path $EngineRoot 'generated_assets\DUKE3D.GRP'
$EngineGrp = Join-Path $EngineRoot 'DUKE3D.GRP'

function Write-Step {
    param([string]$Message)
    if ($Fast) {
        Write-Host "[fast] $Message"
    } else {
        Write-Host $Message
    }
}

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Label
    )

    if (-not (Test-Path $Path)) {
        throw "$Label not found: $Path"
    }
}

function Remove-StaleHeadlessArtifacts {
    foreach ($path in @($CapturesDir, $StartupLog)) {
        if (Test-Path $path) {
            Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    Get-ChildItem -Path $EngineRoot -File -Filter '.headless_run.*' -ErrorAction SilentlyContinue |
        ForEach-Object {
            Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue
        }
}

function Invoke-Python {
    param(
        [string]$Description,
        [string[]]$ArgumentList
    )

    Write-Step $Description
    & python @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE"
    }
}

Set-Location $RepoRoot
$env:DUKE3D_SILENT_ERRORS = '1'
$env:DUKE3D_HEADLESS_RUN_ID = [guid]::NewGuid().Guid

Write-Step 'Building Windows native Release binary'
& $WinBuild -Action build -BuildType release
if ($LASTEXITCODE -ne 0) {
    throw "win_build.ps1 failed with exit code $LASTEXITCODE"
}

if (-not $BuiltExe) {
    throw "Built executable not found at build\Release\duke3d.exe or build\duke3d.exe"
}
Assert-PathExists $EngineExe 'Engine-root executable copy'
Assert-PathExists $EngineDll 'SDL2 runtime DLL'

if ($BuildOnly) {
    Write-Host 'Build-only mode requested; skipping asset generation and tests.'
    exit 0
}

Assert-PathExists $Requirements 'Python requirements'

if ($SkipRequirementsInstall) {
    Write-Step 'Skipping Python requirements install (handled by caller)'
} else {
    Invoke-Python -Description 'Installing Python requirements' -ArgumentList @(
        '-m', 'pip', 'install', '--disable-pip-version-check', '-r', $Requirements
    )
}

Invoke-Python -Description 'Generating procedural assets' -ArgumentList @(
    $GenerateAssets,
    '--no-ai'
)

Assert-PathExists $GeneratedGrp 'Generated-assets DUKE3D.GRP'
Assert-PathExists $EngineGrp 'Engine DUKE3D.GRP'

Remove-StaleHeadlessArtifacts
Invoke-Python -Description 'Running allocache regression' -ArgumentList @(
    '-m', 'pytest', $AllocacheTest, '-q'
)

Remove-StaleHeadlessArtifacts
Invoke-Python -Description 'Running visual playtest' -ArgumentList @(
    '-m', 'pytest', $VisualPlaytest, '-m', 'playtest', '-q'
)

Write-Host 'Native Windows E2E checks completed successfully.'
