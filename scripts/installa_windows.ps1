# Installa Sbobina su Windows 10/11 e mette "Sbobina" sul Desktop.
# Uso (dalla cartella del progetto):
#   powershell -ExecutionPolicy Bypass -File scripts\installa_windows.ps1
# Serve una volta sola. I modelli AI (llama.cpp + Gemma, Whisper) li scarica l'app al primo avvio.
$ErrorActionPreference = "Stop"
$Progetto = Split-Path -Parent $PSScriptRoot
Set-Location $Progetto

# Python 3.12: pythonnet (finestra nativa con WebView2) e i pacchetti CUDA hanno le ruote pronte per questa versione.
cmd /c "py -3.12 --version >nul 2>&1"  # via cmd: in PowerShell 5 lo stderr di un comando con "Stop" diventa un errore
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installo Python 3.12..."
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

if (-not (Test-Path ".venv\Scripts\python.exe")) { & py -3.12 -m venv .venv }
$Py = Join-Path $Progetto ".venv\Scripts\python.exe"
& $Py -m pip install --upgrade pip
& $Py -m pip install -e ".[locale,app,windows]"
if ($LASTEXITCODE -ne 0) { throw "Installazione dei pacchetti non riuscita." }

# ffmpeg statico (pacchetto static-ffmpeg): lo scarica adesso invece che al primo audio.
& $Py -c "import static_ffmpeg; static_ffmpeg.add_paths(); print('ffmpeg pronto')"

# Avvio: dati dello studente in %LOCALAPPDATA%\Sbobina\dati, finestra della console ridotta a icona.
$Avvio = Join-Path $Progetto "Sbobina.cmd"
@"
@echo off
set "SBOBINA_DATI=%LOCALAPPDATA%\Sbobina\dati"
if not exist "%SBOBINA_DATI%" mkdir "%SBOBINA_DATI%"
cd /d "$Progetto"
"$Py" -m sbobina.cli app >> "%LOCALAPPDATA%\Sbobina\sbobina.log" 2>&1
"@ | Set-Content -Encoding ASCII $Avvio
New-Item -ItemType Directory -Force (Join-Path $env:LOCALAPPDATA "Sbobina") | Out-Null

$Collegamento = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath("Desktop")) "Sbobina.lnk"))
$Collegamento.TargetPath = $Avvio
$Collegamento.WorkingDirectory = $Progetto
$Collegamento.WindowStyle = 7  # ridotta a icona
$Collegamento.Save()

Write-Host ""
Write-Host "Fatto. Apri 'Sbobina' dal Desktop."
Write-Host "Se qualcosa non va, il registro e' in $env:LOCALAPPDATA\Sbobina\sbobina.log"
