Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\pip.exe install -r requirements.txt
$env:HOST = if ($env:HOST) { $env:HOST } else { "0.0.0.0" }
$env:PORT = if ($env:PORT) { $env:PORT } else { "8765" }
.\.venv\Scripts\python.exe -m outlook_rt_login.web
