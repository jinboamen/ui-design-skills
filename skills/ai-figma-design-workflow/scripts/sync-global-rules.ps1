[CmdletBinding()]
param(
    [string]$CodexDirectory,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$utf8 = [System.Text.UTF8Encoding]::new($false, $true)
if ([string]::IsNullOrWhiteSpace($CodexDirectory)) {
    $CodexDirectory = $env:CODEX_HOME
}
if ([string]::IsNullOrWhiteSpace($CodexDirectory)) {
    $CodexDirectory = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex'
}
$CodexDirectory = [System.IO.Path]::GetFullPath($CodexDirectory)
$skillDirectory = Split-Path -Parent $PSScriptRoot
$templatePath = Join-Path $skillDirectory 'references/global-figma-rules.md'
$template = [System.IO.File]::ReadAllText($templatePath, $utf8).TrimEnd([char[]]"`r`n")
$startMarker = '<!-- ai-figma-design-workflow:global-rules:start -->'
$endMarker = '<!-- ai-figma-design-workflow:global-rules:end -->'
$blockPattern = '(?s)' + [regex]::Escape($startMarker) + '.*?' + [regex]::Escape($endMarker)

if (!$template.StartsWith($startMarker) -or !$template.EndsWith($endMarker)) {
    throw 'Global Figma rules template has invalid boundary markers.'
}

$targetPaths = @(Join-Path $CodexDirectory 'AGENTS.md')
$overridePath = Join-Path $CodexDirectory 'AGENTS.override.md'
if ([System.IO.File]::Exists($overridePath)) {
    $overrideText = [System.IO.File]::ReadAllText($overridePath, $utf8)
    if (![string]::IsNullOrWhiteSpace($overrideText)) {
        $targetPaths += $overridePath
    }
}

# Prepare every update before writing, so malformed markers fail without changes.
$updates = foreach ($targetPath in $targetPaths) {
    $original = ''
    if ([System.IO.File]::Exists($targetPath)) {
        $original = [System.IO.File]::ReadAllText($targetPath, $utf8)
    }
    $startCount = [regex]::Matches($original, [regex]::Escape($startMarker)).Count
    $endCount = [regex]::Matches($original, [regex]::Escape($endMarker)).Count
    if ($startCount -ne $endCount -or $startCount -gt 1) {
        throw "Global Figma rules markers require repair in $targetPath"
    }

    $newline = "`n"
    if ($original.Contains("`r`n")) {
        $newline = "`r`n"
    }
    $block = ($template -replace "`r`n", "`n") -replace "`n", $newline
    if ($startCount -eq 1) {
        $match = [regex]::Match($original, $blockPattern)
        if (!$match.Success) {
            throw "Global Figma rules markers are out of order in $targetPath"
        }
        $updated = $original.Substring(0, $match.Index) + $block +
            $original.Substring($match.Index + $match.Length)
    } else {
        $separator = ''
        if ($original.Length -gt 0) {
            $separator = $newline + $newline
            if ($original.EndsWith($newline + $newline)) {
                $separator = ''
            } elseif ($original.EndsWith($newline)) {
                $separator = $newline
            }
        }
        $updated = $original + $separator + $block + $newline
    }
    [pscustomobject]@{
        Path = $targetPath
        Content = $updated
        Changed = $updated -cne $original
    }
}

if ($Check) {
    foreach ($update in $updates) {
        if ($update.Changed) {
            Write-Output "Needs sync $($update.Path)"
        } else {
            Write-Output "Verified $($update.Path)"
        }
    }
    if (@($updates | Where-Object Changed).Count -gt 0) {
        exit 1
    }
    exit 0
}

[System.IO.Directory]::CreateDirectory($CodexDirectory) | Out-Null
foreach ($update in $updates) {
    if ($update.Changed) {
        [System.IO.File]::WriteAllText($update.Path, $update.Content, $utf8)
        Write-Output "Updated $($update.Path)"
    } else {
        Write-Output "Already synced $($update.Path)"
    }
}
