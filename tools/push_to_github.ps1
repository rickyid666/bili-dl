# Push bili-dl to GitHub over HTTPS (no gh CLI needed).
#
# Usage:
#   $env:GH_TOKEN = 'ghp_xxxxxxxx'          # classic PAT with "repo" scope
#   .\tools\push_to_github.ps1 -Repo "yourname/bili-dl" -Create
#
#   -Create   create the repo on GitHub first (needs the token)
#   If -Create is omitted, the repo must already exist and be empty.
#
# The token is only used for the duration of the push: it is injected into the
# remote URL for that single command and stripped again afterwards, so it never
# stays in .git/config.

param(
    [Parameter(Mandatory = $true)][string]$Repo,
    [switch]$Create,
    [string]$Token = $env:GH_TOKEN,
    [string]$Description = "Bilibili video downloader: paste a URL, get a losslessly merged MP4.",
    [switch]$Private
)

$ErrorActionPreference = 'Stop'
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

$headers = @{ Authorization = "token $Token"; 'User-Agent' = 'bili-dl-push' }

if ($Create) {
    Write-Host "[1/4] Creating GitHub repo $Repo ..."
    $body = @{ name = ($Repo -split '/')[1]; description = $Description; private = [bool]$Private } | ConvertTo-Json
    try {
        $null = Invoke-RestMethod -Uri 'https://api.github.com/user/repos' -Method Post -Headers $headers `
            -Body $body -ContentType 'application/json'
        Write-Host "      created."
    }
    catch {
        $msg = $_.Exception.Message
        if ($msg -match '422') { Write-Host "      already exists, continuing." }
        else { Write-Host "      FAILED: $msg" -ForegroundColor Red; exit 1 }
    }
}

$credUrl = "https://$Token@github.com/$Repo.git"
$bareUrl = "https://github.com/$Repo.git"

try {
    Write-Host "[2/4] Setting remote ..."
    git remote remove origin 2>$null | Out-Null
    git remote add origin $credUrl

    Write-Host "[3/4] Pushing main ..."
    git push -u origin main
    if ($LASTEXITCODE -ne 0) { throw "git push failed (exit $LASTEXITCODE)" }
}
finally {
    Write-Host "[4/4] Stripping token from .git/config ..."
    git remote set-url origin $bareUrl 2>$null
    # 某些受限环境里 git 会留下 config.lock 让 set-url 失败，清掉后再试一次
    if (Test-Path '.git/config.lock') {
        Remove-Item '.git/config.lock' -Force -ErrorAction SilentlyContinue
        if (Test-Path '.git/config.lock') {
            cmd /c 'del /f /q ".git\config.lock"' 2>$null | Out-Null
        }
        git remote set-url origin $bareUrl 2>$null
    }
    $cfg = Get-Content '.git/config' -Raw
    if ($cfg -match [regex]::Escape($Token)) {
        Write-Host "      WARNING: token STILL in .git/config - clean it manually!" -ForegroundColor Red
    }
    else {
        Write-Host "      done, token removed."
    }
}

Write-Host ""
Write-Host "OK -> $bareUrl" -ForegroundColor Green
Write-Host "Check:  git remote -v   /   git log --oneline"
