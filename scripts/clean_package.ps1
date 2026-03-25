$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot

Get-ChildItem -Path $root -Recurse -Directory |
    Where-Object { $_.Name -eq "__pycache__" } |
    Remove-Item -Recurse -Force

Get-ChildItem -Path $root -Recurse -File |
    Where-Object { $_.Extension -in ".pyc", ".pyo" } |
    Remove-Item -Force

Write-Host "Removed __pycache__ directories and compiled Python files."
