param([string]$Address,[int]$Port=8777)
$readerRoot = Split-Path -Parent $PSScriptRoot
if (-not $Address) {
    Write-Host '先选择与手机同一Wi-Fi的电脑IPv4地址：'
    Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -match '^(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)' } | Format-Table InterfaceAlias,IPAddress
    $Address = Read-Host '输入上表中的Wi-Fi IPv4地址'
}
$readerPython = Join-Path $readerRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $readerPython)) { $readerPython = Join-Path $readerRoot '../../maintenance/product-suite/.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $readerPython)) { $readerPython = 'python' }
Push-Location $readerRoot
try { & $readerPython -m app.lan --host $Address --port $Port }
finally { Pop-Location }
