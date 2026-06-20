<#
.SYNOPSIS
    Static-analysis (SAST) scan of the Atomic Shell / Duke3D engine for
    app-breaking Win64 bugs - chiefly 32-bit `long` <-> 64-bit pointer
    truncation, which is what crashed the software renderer historically.

.DESCRIPTION
    Configures a throwaway Debug build of the engine with -DATOMIC_SAST=ON
    (which re-enables MSVC warnings C4311/C4312/C4302/C4826 + C4244/C4267 that
    the normal /W0 build suppresses), builds it capturing all compiler output,
    parses the warnings, and writes a triaged Markdown report.

    HIGH  = C4311/C4312/C4302/C4826  (pointer truncation / sign-extension)
    MED   = C4244/C4267              (integer / size_t narrowing)
    ANLZ  = C6xxx                    (only with -Analyze: null deref, overrun...)

    Exit code = number of HIGH findings (0 = clean), so it works as wgm
    backpressure.

.PARAMETER Analyze
    Also pass /analyze:only (deeper, slower C6xxx checks).

.PARAMETER EngineRoot
    Path to the engine source root (default: auto-detected).
#>
[CmdletBinding()]
param(
    [switch]$Analyze,
    [string]$EngineRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# --- Resolve paths ----------------------------------------------------------
$ScriptDir = Split-Path -Parent $PSCommandPath
if (-not $EngineRoot) {
    # engine/tools/sast_scan.ps1 -> engine root is one level up.
    $EngineRoot = Split-Path -Parent $ScriptDir
}
$EngineRoot = (Resolve-Path $EngineRoot).Path
$RepoRoot   = Split-Path -Parent $EngineRoot
$BuildDir   = Join-Path $EngineRoot 'build-sast'
$RawLog     = Join-Path $BuildDir 'sast_raw.log'
$ReportDir  = Join-Path $RepoRoot 'docs\agent'
$Report     = Join-Path $ReportDir 'SAST_FINDINGS.md'

if (-not (Test-Path (Join-Path $EngineRoot 'CMakeLists.txt'))) {
    throw "Engine CMakeLists.txt not found under $EngineRoot"
}

# --- Locate vcvars64.bat ----------------------------------------------------
# Prefer vswhere (the same discovery win_build.ps1 uses): hosted CI runners and
# many dev boxes install Visual Studio at a path that is NOT in the fixed
# candidate list below, so a hardcoded-only probe wrongly fails on CI even though
# the toolchain is present. Fall back to the fixed list when vswhere is absent.
$vcvars = $null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (Test-Path $vswhere) {
    $vsPath = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Workload.NativeDesktop -property installationPath
    if ($vsPath) {
        $candidate = Join-Path $vsPath.Trim() 'VC\Auxiliary\Build\vcvars64.bat'
        if (Test-Path $candidate) { $vcvars = $candidate }
    }
}
if (-not $vcvars) {
    $vcCandidates = @(
        "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat",
        "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat",
        "C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat"
    )
    $vcvars = $vcCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $vcvars) { throw "vcvars64.bat not found. Install MSVC Build Tools." }

# --- Configure + build (Debug => no LTO => fast; warnings still emit) --------
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
$analyzeFlag = if ($Analyze) { '-DATOMIC_SAST_ANALYZE=ON' } else { '' }
$CfgLog = Join-Path $BuildDir 'sast_configure.log'

# Redirect all output to a file INSIDE cmd so PowerShell never sees a stderr
# stream (CMake's non-fatal vswhere probe writes to stderr, which would trip
# $ErrorActionPreference='Stop').
Write-Host "=== SAST: configuring engine/build-sast (ATOMIC_SAST=ON) ===" -ForegroundColor Cyan
$cfgCmd = "call `"$vcvars`" >nul 2>&1 && cmake -S `"$EngineRoot`" -B `"$BuildDir`" -G Ninja -DCMAKE_BUILD_TYPE=Debug -DATOMIC_SAST=ON $analyzeFlag > `"$CfgLog`" 2>&1"
& $env:ComSpec /c $cfgCmd | Out-Null
if (-not (Test-Path (Join-Path $BuildDir 'build.ninja'))) {
    Get-Content $CfgLog -Tail 30 | Write-Host
    throw "SAST configure failed (no build.ninja). See $CfgLog"
}

Write-Host "=== SAST: compiling (capturing warnings) ===" -ForegroundColor Cyan
& $env:ComSpec /c "call `"$vcvars`" >nul 2>&1 && cmake --build `"$BuildDir`" --target clean >> `"$CfgLog`" 2>&1" | Out-Null
$buildCmd = "call `"$vcvars`" >nul 2>&1 && cmake --build `"$BuildDir`" -j 4 > `"$RawLog`" 2>&1"
& $env:ComSpec /c $buildCmd | Out-Null

if (-not (Test-Path $RawLog)) { throw "No build output captured at $RawLog" }

# --- Parse warnings ---------------------------------------------------------
# MSVC: <file>(<line>): warning C####: <message>
$rx = [regex]'^(?<file>.+?)\((?<line>\d+)\)\s*:\s*warning\s+(?<code>C\d{4,5})\s*:\s*(?<msg>.*)$'
$HIGH = @('C4311','C4312','C4302','C4826')
$MED  = @('C4244','C4267')

$seen = New-Object System.Collections.Generic.HashSet[string]
$findings = New-Object System.Collections.Generic.List[object]

foreach ($line in Get-Content -Path $RawLog) {
    $m = $rx.Match($line)
    if (-not $m.Success) { continue }
    $code = $m.Groups['code'].Value
    $file = $m.Groups['file'].Value.Trim()
    $ln   = [int]$m.Groups['line'].Value
    $msg  = $m.Groups['msg'].Value.Trim()
    # Normalize file path to repo-relative when possible.
    try { $file = (Resolve-Path $file -ErrorAction Stop).Path } catch {}
    if ($file.StartsWith($RepoRoot)) { $file = $file.Substring($RepoRoot.Length).TrimStart('\','/') }
    $key = "$file|$ln|$code"
    if (-not $seen.Add($key)) { continue }   # dedup
    $sev = if ($HIGH -contains $code) { 'HIGH' }
           elseif ($MED -contains $code) { 'MED' }
           elseif ($code -like 'C6*') { 'ANLZ' }
           else { 'INFO' }
    $findings.Add([pscustomobject]@{ Sev=$sev; Code=$code; File=$file; Line=$ln; Msg=$msg })
}

$high = @($findings | Where-Object Sev -eq 'HIGH')
$med  = @($findings | Where-Object Sev -eq 'MED')
$anlz = @($findings | Where-Object Sev -eq 'ANLZ')

# --- Write report -----------------------------------------------------------
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$sb = New-Object System.Text.StringBuilder
function Add-Line($s) { [void]$sb.AppendLine($s) }

Add-Line "# SAST Findings - Atomic Shell engine"
Add-Line ""
Add-Line "Generated by ``tools/sast_scan.ps1`` (MSVC truncation warnings$(if($Analyze){' + /analyze'})). "
Add-Line "Run: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
Add-Line ""
Add-Line "## Summary"
Add-Line ""
Add-Line "| Severity | Meaning | Count |"
Add-Line "|---|---|---|"
Add-Line "| HIGH | pointer truncation / sign-extension (C4311/C4312/C4302/C4826) - app-breaking | $($high.Count) |"
Add-Line "| MED  | integer / size_t narrowing (C4244/C4267) - usually benign fixed-point | $($med.Count) |"
Add-Line "| ANLZ | /analyze crash-class (C6xxx) | $($anlz.Count) |"
Add-Line ""
Add-Line "HIGH findings are the crash class that produced the historical renderer"
Add-Line "access violation (``waloff[globalpicnum] = 0xFFFFFFFFCC946840``). Each must be"
Add-Line "triaged: real pointer<->long round-trip (fix) or benign (document)."
Add-Line ""

function Add-Section($title, $items) {
    Add-Line "## $title ($($items.Count))"
    Add-Line ""
    if ($items.Count -eq 0) { Add-Line "_None._"; Add-Line ""; return }
    # group by code
    foreach ($g in ($items | Group-Object Code | Sort-Object Name)) {
        Add-Line "### $($g.Name) - $($g.Count)"
        Add-Line ""
        foreach ($f in ($g.Group | Sort-Object File,Line)) {
            Add-Line "- ``$($f.File):$($f.Line)`` - $($f.Msg)"
        }
        Add-Line ""
    }
}

Add-Section "HIGH - pointer truncation / sign-extension" $high
Add-Section "MED - integer / size_t narrowing" $med
if ($Analyze) { Add-Section "ANLZ - /analyze (C6xxx)" $anlz }

[System.IO.File]::WriteAllText($Report, $sb.ToString())

# --- Console summary --------------------------------------------------------
Write-Host ""
Write-Host "=== SAST summary ===" -ForegroundColor Cyan
$highColor = if ($high.Count) { 'Red' } else { 'Green' }
Write-Host ("  HIGH (pointer truncation) : {0}" -f $high.Count) -ForegroundColor $highColor
Write-Host ("  MED  (narrowing)          : {0}" -f $med.Count)
if ($Analyze) { Write-Host ("  ANLZ (/analyze C6xxx)     : {0}" -f $anlz.Count) }
Write-Host ("  Report: {0}" -f $Report)
if ($high.Count -gt 0) {
    Write-Host ""
    Write-Host "HIGH findings (file:line):" -ForegroundColor Yellow
    foreach ($f in ($high | Sort-Object File,Line)) {
        Write-Host ("  [{0}] {1}:{2}" -f $f.Code, $f.File, $f.Line)
    }
}

exit [math]::Min($high.Count, 250)
