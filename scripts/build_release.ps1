$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$pluginName = Split-Path -Leaf $root
$distDir = Join-Path $root "dist"
$stageRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("{0}_release_stage" -f $pluginName)
$stagePluginDir = Join-Path $stageRoot $pluginName

& (Join-Path $PSScriptRoot "clean_package.ps1")

$metadataPath = Join-Path $root "metadata.txt"
$versionMatch = Select-String -Path $metadataPath -Pattern '^\s*version\s*=' | Select-Object -First 1
if (-not $versionMatch) {
    throw "Missing version field in metadata.txt."
}
$version = ($versionMatch.Line -replace '^\s*version\s*=', '').Trim()
if (-not $version) {
    throw "Version value in metadata.txt is empty."
}

if (Test-Path $stageRoot) {
    Remove-Item -Recurse -Force $stageRoot
}
New-Item -ItemType Directory -Path $stagePluginDir -Force | Out-Null
New-Item -ItemType Directory -Path $distDir -Force | Out-Null

Get-ChildItem -Path $root -Recurse -File | ForEach-Object {
    $fullPath = $_.FullName
    $relativePath = $fullPath.Substring($root.Length).TrimStart('\')
    $normalized = $relativePath -replace '/', '\'
    $skip =
        $normalized -eq '.gitignore' -or
        $normalized -eq 'build_release.bat' -or
        $normalized -eq 'WORKING_PRINCIPLE.md' -or
        $normalized -eq 'resources\icon.svg' -or
        $normalized.StartsWith('docs\') -or
        $normalized.StartsWith('scripts\') -or
        $normalized.Contains('\__pycache__\') -or
        $normalized.EndsWith('.pyc') -or
        $normalized.EndsWith('.pyo') -or
        $normalized.EndsWith('.zip')
    if ($skip) {
        return
    }
    $targetPath = Join-Path $stagePluginDir $normalized
    $targetDir = Split-Path -Parent $targetPath
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }
    Copy-Item -Path $fullPath -Destination $targetPath -Force
}

$zipName = "{0}-{1}.zip" -f $pluginName, $version
$zipPath = Join-Path $distDir $zipName
if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}

Compress-Archive -Path $stagePluginDir -DestinationPath $zipPath -Force
Remove-Item -Recurse -Force $stageRoot

Write-Host "Release package created: $zipPath"
