<#
  SentinelAI - fetch real vulnerability feeds, ingest them, and print the run commands.
  Run from the repo root:   powershell -ExecutionPolicy Bypass -File .\scripts\setup_experiment.ps1

  Auto-downloads the two single-file public feeds (EPSS + CISA KEV). The phishing and
  code corpora are larger / licensed and are downloaded manually (links printed below).
#>
$ErrorActionPreference = "Stop"
$py   = ".\backend\.venv\Scripts\python.exe"
$data = "data"
New-Item -ItemType Directory -Force -Path $data | Out-Null

Write-Host "1/3  Downloading EPSS scores (FIRST) ..." -ForegroundColor Cyan
Invoke-WebRequest "https://epss.cyentia.com/epss_scores-current.csv.gz" -OutFile "$data\epss.csv.gz"
# gunzip
$in  = [System.IO.File]::OpenRead("$data\epss.csv.gz")
$gz  = New-Object System.IO.Compression.GzipStream($in, [System.IO.Compression.CompressionMode]::Decompress)
$out = [System.IO.File]::Create("$data\epss.csv")
$gz.CopyTo($out); $out.Close(); $gz.Close(); $in.Close()

Write-Host "2/3  Downloading CISA KEV catalogue ..." -ForegroundColor Cyan
Invoke-WebRequest "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json" -OutFile "$data\kev.json"

Write-Host "3/3  Ingesting CVEs into eval/datasets/full/ ..." -ForegroundColor Cyan
& $py -m eval.datasets.ingest cves --epss "$data\epss.csv" --kev "$data\kev.json" --limit 2000

Write-Host ""
Write-Host "CVE dataset ready (top 2000 by EPSS)." -ForegroundColor Green
Write-Host ""
Write-Host "Manual (larger corpora):" -ForegroundColor Yellow
Write-Host "  Phishing : download Nazario + SpamAssassin corpora, then:"
Write-Host "     $py -m eval.datasets.ingest emails --phish .\data\phish --ham .\data\ham --limit 1000"
Write-Host "  Code     : download OWASP Benchmark / Juliet, build a manifest.csv (file,vulnerable,cwe), then:"
Write-Host "     $py -m eval.datasets.ingest code --manifest .\data\benchmark\manifest.csv"
Write-Host ""
Write-Host "Then run the experiment (Ollama must be running):" -ForegroundColor Cyan
Write-Host "  $py -m eval.run_experiment --model llama3.2 --repeats 3"
Write-Host "  $py -m eval.notebooks.generate_figures"
Write-Host ""
Write-Host "Tip: run across models to compare capability:" -ForegroundColor DarkGray
Write-Host "  foreach (`$m in 'llama3.2','mistral') { $py -m eval.run_experiment --model `$m --repeats 3 }"
