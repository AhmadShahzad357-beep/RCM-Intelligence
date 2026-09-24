$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Step 1/13: Load MA SCP enrollment data..." -ForegroundColor Cyan
python -m src.data.load_ma_scp

Write-Host "Step 2/13: Growth analysis..." -ForegroundColor Cyan
python -m src.analysis.growth

Write-Host "Step 3/13: Rolling-origin backtest..." -ForegroundColor Cyan
python -m src.models.backtest

Write-Host "Step 4/13: Prophet forecast..." -ForegroundColor Cyan
python -m src.models.forecast_prophet

Write-Host "Step 5/13: Growth opportunity scoring..." -ForegroundColor Cyan
python -m src.models.opportunity_scoring

Write-Host "Step 6/13: PA classifier (CMS PBP benefit exposure)..." -ForegroundColor Cyan
python -m src.models.pa_classifier

Write-Host "Step 7/13: Load CPSC enrollment data..." -ForegroundColor Cyan
python -m src.data.load_cpsc

Write-Host "Step 8/13: Member-weighted PA exposure score..." -ForegroundColor Cyan
python -m src.models.pa_exposure_score

Write-Host "Step 9/13: Load CPSC payer-level data..." -ForegroundColor Cyan
python -m src.data.load_cpsc_payer

Write-Host "Step 10/13: Payer scorecard..." -ForegroundColor Cyan
python -m src.models.payer_scorecard

Write-Host "Step 11/13: Hierarchical (state/county) forecast..." -ForegroundColor Cyan
python -m src.models.hierarchical_forecast

Write-Host "Step 12/13: Proxy revenue scenarios..." -ForegroundColor Cyan
python -m src.models.proxy_revenue

Write-Host "Step 13/13: Validation summary..." -ForegroundColor Cyan
python -m src.models.evaluate

Write-Host "`nPipeline complete." -ForegroundColor Green
