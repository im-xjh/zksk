param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$InputPath,

    [Parameter(Position = 1)]
    [string]$OutputPath,

    [switch]$Open
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$toolPath = Join-Path $scriptDir "md_to_word_report.py"

$pythonCandidates = @(
    (Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "python",
    "py"
)

$python = $null
foreach ($candidate in $pythonCandidates) {
    try {
        $cmd = Get-Command $candidate -ErrorAction Stop
        $python = $cmd.Source
        break
    } catch {
        if (Test-Path -LiteralPath $candidate) {
            $python = $candidate
            break
        }
    }
}

if (-not $python) {
    throw "Python was not found. Install Python or run this from Codex, where the bundled Python is available."
}

$argsList = @($toolPath, $InputPath)
if ($OutputPath) {
    $argsList += @("--output", $OutputPath)
}

$result = & $python @argsList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host $result
if ($Open) {
    Invoke-Item -LiteralPath $result
}
