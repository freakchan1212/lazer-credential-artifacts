$ErrorActionPreference = 'Stop'
try {
    $root = Split-Path -Parent $PSScriptRoot
    $gitCmd = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($gitCmd) {
        $git = $gitCmd.Source
    } else {
        $desktop = Join-Path $env:LOCALAPPDATA 'GitHubDesktop'
        $candidates = @(Get-ChildItem -Path (Join-Path $desktop 'app-*\resources\app\git\cmd\git.exe') -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
        if ($candidates.Count -eq 0) { throw 'Git was not found. Install/open GitHub Desktop, then retry.' }
        $git = $candidates[0].FullName
    }
    $top = & $git -C $root rev-parse --show-toplevel
    if ($LASTEXITCODE -ne 0) { throw 'This directory is not an existing Git repository. Keep the original local .git directory.' }
    if ([IO.Path]::GetFullPath($top.Trim()).TrimEnd('\','/') -ine [IO.Path]::GetFullPath($root).TrimEnd('\','/')) { throw 'Repository root does not match the package directory.' }
    $manifestPath = Join-Path $root 'SHA256_MANIFEST.json'
    $manifest = [IO.File]::ReadAllText($manifestPath, [Text.Encoding]::UTF8) | ConvertFrom-Json
    $names = @()
    foreach ($entry in $manifest.sha256.PSObject.Properties) {
        $name = $entry.Name
        if ([IO.Path]::IsPathRooted($name) -or $name -match '(^|/)\.\.(/|$)') { throw 'Unsafe manifest path.' }
        $path = Join-Path $root $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing file: $name" }
        $actual = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        if ($actual -ine [string]$entry.Value) { throw "Changed file: $name. Do not regenerate the manifest to hide an unexpected change." }
        $names += $name
    }
    Write-Host ('CHECK PASSED: ' + $names.Count + ' manifest files.')
    $names += 'SHA256_MANIFEST.json'
    for ($i = 0; $i -lt $names.Count; $i += 20) {
        $last = [Math]::Min($i + 19, $names.Count - 1)
        $batch = @($names[$i..$last])
        & $git -C $root add -f -- @batch
        if ($LASTEXITCODE -ne 0) { throw 'git add failed. Review the error before proceeding.' }
    }
    Write-Host 'STAGING PASSED. All manifest files have been added to the Git index.'
    Write-Host 'No commit, push or remote release was performed.'
    Write-Host 'Return to GitHub Desktop, review Changes, then Commit and Push.'
} catch {
    Write-Host ('FAILED: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
