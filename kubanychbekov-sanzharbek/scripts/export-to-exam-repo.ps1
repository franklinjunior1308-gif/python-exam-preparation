# Copies the project CONTENTS (not the folder itself) into the root of the private exam repository.
# Usage (PowerShell), from anywhere:
#   .\scripts\export-to-exam-repo.ps1 -Target C:\work\exam-repo            # real copy
#   .\scripts\export-to-exam-repo.ps1 -Target C:\temp\dry-run -DryRun      # copy to a scratch folder and print checks
# Never copies .git, build output, caches, virtual environments, .env, APKs or uploads.
param(
  [Parameter(Mandatory = $true)][string]$Target,
  [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$src = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
New-Item -ItemType Directory -Force -Path $Target | Out-Null
$xd = @(".git", "node_modules", ".next", "build", ".dart_tool", ".gradle", ".kotlin", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "uploads", ".idea", ".vscode")
$xf = @(".env", "*.apk", "local.properties", "*.iml")
robocopy $src $Target /E /XD $xd /XF $xf /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with code $LASTEXITCODE" }

Write-Host "--- checks in $Target"
$required = @("README.md", "compose.yaml", "Makefile", ".env.example", ".gitignore",
  "backend\pyproject.toml", "backend\uv.lock", "backend\alembic", "backend\app", "backend\tests",
  "web\package.json", "web\bun.lock", "mobile\pubspec.yaml", "mobile\pubspec.lock", "mobile\lib", "mobile\test", "mobile\android",
  "scripts\verify-all.sh", "scripts\smoke.sh", "docs\AI_USAGE.md", "docs\ARCHITECTURE.md", "docs\API.md",
  "docs\PRODUCT_DECISIONS.md", "docs\KNOWN_LIMITATIONS.md", "docs\VERIFICATION.md")
$missing = $required | Where-Object { -not (Test-Path (Join-Path $Target $_)) }
if ($missing) { Write-Host "MISSING: $($missing -join ', ')" -ForegroundColor Red } else { Write-Host "required layout: OK" }
if (Test-Path (Join-Path $Target "kubanychbekov-sanzharbek")) { Write-Host "ERROR: nested project folder exists" -ForegroundColor Red }
if (Test-Path (Join-Path $Target ".env")) { Write-Host "ERROR: .env present" -ForegroundColor Red }
$gits = Get-ChildItem -Recurse -Force -Directory -Filter .git -Path $Target | Where-Object { $_.FullName -ne (Join-Path $Target ".git") }
if ($gits) { Write-Host "ERROR: nested .git found" -ForegroundColor Red }
$big = Get-ChildItem -Recurse -File -Path $Target | Where-Object { $_.Length -gt 5MB -and $_.FullName -notlike "*\.git\*" }
if ($big) { $big | ForEach-Object { Write-Host "LARGE FILE: $($_.FullName) $([math]::Round($_.Length/1MB,1)) MB" -ForegroundColor Yellow } }
$size = (Get-ChildItem -Recurse -File -Path $Target | Where-Object { $_.FullName -notlike "*\.git\*" } | Measure-Object Length -Sum).Sum
Write-Host ("total size: {0:N1} MB" -f ($size / 1MB))
$todo = Select-String -Path (Join-Path $Target "README.md") -Pattern "TODO" -SimpleMatch
if ($todo) { Write-Host "README.md still has a TODO (YouTube link): $($todo[0].Line)" -ForegroundColor Yellow }
if ($DryRun) { Write-Host "dry run finished (nothing was pushed)." }
