param(
    [string]$Distro = "",
    [switch]$BindOnly,
    [switch]$AttachOnly
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
    throw "usbipd command was not found. Install usbipd-win first."
}

$listOutput = usbipd list
$pm3Rows = @($listOutput | Where-Object { $_ -match "0425:0000" })

if (-not $pm3Rows -or $pm3Rows.Count -eq 0) {
    throw "No PM3 devices with VID:PID 0425:0000 were found in 'usbipd list'."
}

$busIds = @()
foreach ($row in $pm3Rows) {
    $parts = (($row -replace "\s+", " ").Trim()).Split(" ")
    if ($parts.Count -gt 0 -and $parts[0] -match "^[0-9]+-[0-9]+$") {
        $busIds += $parts[0]
    }
}

if (-not $busIds -or $busIds.Count -eq 0) {
    throw "Failed to parse BUSID values from usbipd output."
}

$busIds = $busIds | Sort-Object -Unique

foreach ($busId in $busIds) {
    if (-not $AttachOnly) {
        Write-Host "Binding PM3 $busId ..."
        usbipd bind --busid $busId | Out-Host
    }

    if (-not $BindOnly) {
        Write-Host "Attaching PM3 $busId to WSL ..."
        if ($Distro) {
            usbipd attach --wsl --distribution $Distro --busid $busId | Out-Host
        } else {
            usbipd attach --wsl --busid $busId | Out-Host
        }
    }
}

Write-Host "Done. Attached PM3 BUSIDs: $($busIds -join ', ')"
