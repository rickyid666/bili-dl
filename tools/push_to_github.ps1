# Push bili-dl to GitHub over HTTPS (no gh CLI needed).
#
# Usage:
#   $env:GH_TOKEN = 'ghp_xxxxxxxx'          # classic PAT with "repo" scope
#   .\tools\push_to_github.ps1 -Repo "yourname/bili-dl" -Create
#
#   -Create   create the repo on GitHub first (needs the token)
#   If -Create is omitted, the repo must already exist.
#
# Design note: the token is handed to a single `git push` command line and is
# NEVER written into .git/config. The earlier approach (inject the token into
# remote.origin.url, then strip it afterwards) left a cleanup step that a stale
# .git/config.lock could silently break -- which left the token sitting in
# .git/config twice. Keeping origin token-free removes that whole failure mode.
#
# The trade-off: the token is visible in this process's command line for the
# duration of the push. Use a short-lived, single-repo token and revoke it when
# you are done.

param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [switch]$Create,
    [string]$Token = $env:GH_TOKEN,
    [string]$Description = "Bilibili video downloader: paste a URL, get a losslessly merged MP4.",
    [switch]$Private
)

# 'Continue', not 'Stop': git writes normal progress ("Everything up-to-date",
# "To https://...") to stderr, and PowerShell turns that into a terminating
# NativeCommandError under 'Stop'. Failures are detected via $LASTEXITCODE.
$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $here

if (-not $Token) {
    Write-Host "[!] No token. Set it first:  `$env:GH_TOKEN = 'ghp_xxxx'" -ForegroundColor Yellow
    exit 1
}
if ($Repo -notmatch '^[^/]+/[^/]+$') {
    Write-Host "[!] -Repo must look like  owner/name" -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path '.git')) {
    Write-Host "[!] Not a git repository: $here" -ForegroundColor Yellow
    exit 1
}

$bareUrl = "https://github.com/$Repo.git"
$pushUrl = "https://$Token@github.com/$Repo.git"
$headers = @{ Authorization = "token $Token"; 'User-Agent' = 'bili-dl-push' }

if ($Create) {
    Write-Host "[1/3] Creating GitHub repo $Repo ..."
    $body = @{ name = ($Repo -split '/')[1]; description = $Description; private = [bool]$Private } | ConvertTo-Json
    try {
        $null = Invoke-RestMethod -Uri 'https://api.github.com/user/repos' -Method Post -Headers $headers `
            -Body $body -ContentType 'application/json'
        Write-Host "      created."
    }
    catch {
        if ($_.Exception.Message -match '422') { Write-Host "      already exists, continuing." }
        else { Write-Host "      FAILED: $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
    }
}

Write-Host "[2/3] Setting remote (token-free) ..."
git remote remove origin 2>$null | Out-Null
git remote add origin $bareUrl

Write-Host "[3/3] Pushing main ..."
# Merge stderr into the pipeline so PowerShell does not dress git's normal
# progress output up as a NativeCommandError.
git push $pushUrl "refs/heads/main:refs/heads/main" 2>&1 | ForEach-Object { Write-Host "      $_" }
if ($LASTEXITCODE -ne 0) {
    Write-Host "      push FAILED (exit $LASTEXITCODE)" -ForegroundColor Red
    exit 1
}
git branch --set-upstream-to=origin/main main 2>&1 | Out-Null
if (Test-Path '.git/config.lock') {
    Write-Host "[cleanup] removing stale .git/config.lock ..."
    Remove-Item '.git/config.lock' -Force -ErrorAction SilentlyContinue
    if (Test-Path '.git/config.lock') { cmd /c 'del /f /q ".git\config.lock"' 2>$null | Out-Null }
}

$cfg = if (Test-Path '.git/config') { Get-Content '.git/config' -Raw } else { '' }
if ($cfg -match [regex]::Escape($Token)) {
    Write-Host "[!] token found in .git/config - clean it manually!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "OK -> $bareUrl" -ForegroundColor Green
Write-Host "     .git/config is token-free; revoke the PAT when you are done."
exit 0
