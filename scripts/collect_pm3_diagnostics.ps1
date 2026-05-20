param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$OutputDir = "./data/pm3-capture"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "collect_pm3_diagnostics.py"

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python $PythonScript $BaseUrl $OutputDir
    exit $LASTEXITCODE
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py $PythonScript $BaseUrl $OutputDir
    exit $LASTEXITCODE
}

throw "Python is not available in PATH."
