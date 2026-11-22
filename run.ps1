<#
AyurMitra -- One-command setup + run (Windows PowerShell)
Usage:
  .\run.ps1                 # Create .venv if needed, install core deps, build KG v2 if missing, start website + API
  .\run.ps1 -Neural         # Also install IndicTrans2 / sentence-transformers / LLM extras
  .\run.ps1 -Voice          # Also install faster-whisper / edge-tts / gTTS (needs ffmpeg: winget install Gyan.FFmpeg)
  .\run.ps1 -Test           # Run the full test suite instead of the server
  .\run.ps1 -Streamlit      # Run the legacy Streamlit interface
#>
[CmdletBinding()]
param(
    [switch]$Neural,
    [switch]$Voice,
    [switch]$Test,
    [switch]$Streamlit,
    [int]$Port = 0
)

$ErrorActionPreference = "Stop"

# Ensure working directory is the script root (handles paths with spaces safely)
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Definition }
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }
Set-Location -LiteralPath $ScriptDir

# Resolve port from argument, environment, or default 8000
if ($Port -le 0) {
    if ($env:AYUR_PORT) {
        $Port = [int]$env:AYUR_PORT
    } else {
        $Port = 8000
    }
}

try {
    # 1. Virtual Environment Creation & Path setup
    $venvDir = Join-Path -Path $ScriptDir -ChildPath ".venv"
    $py = Join-Path -Path $venvDir -ChildPath "Scripts\python.exe"

    if (-not (Test-Path -LiteralPath $py)) {
        Write-Host "Creating Python virtual environment in .venv..." -ForegroundColor Cyan
        $venvCreated = $false

        # Try py launcher with Python 3.13 first
        try {
            $process = Start-Process -FilePath "py" -ArgumentList "-3.13", "-m", "venv", "`"$venvDir`"" -NoNewWindow -Wait -PassThru -ErrorAction SilentlyContinue
            if ($process.ExitCode -eq 0 -and (Test-Path -LiteralPath $py)) {
                $venvCreated = $true
            }
        } catch {}

        # Fall back to standard python on PATH
        if (-not $venvCreated) {
            try {
                $process = Start-Process -FilePath "python" -ArgumentList "-m", "venv", "`"$venvDir`"" -NoNewWindow -Wait -PassThru -ErrorAction SilentlyContinue
                if ($process.ExitCode -eq 0 -and (Test-Path -LiteralPath $py)) {
                    $venvCreated = $true
                }
            } catch {}
        }

        if (-not (Test-Path -LiteralPath $py)) {
            throw "Failed to create virtual environment (.venv). Please ensure Python 3.13 or Python 3 is installed."
        }
        Write-Host "Virtual environment created successfully." -ForegroundColor Green
    }

    # 2. Virtual Environment Activation
    $activateScript = Join-Path -Path $venvDir -ChildPath "Scripts\Activate.ps1"
    if (Test-Path -LiteralPath $activateScript) {
        try {
            . $activateScript
        } catch {
            Write-Warning "Could not dot-source Activate.ps1 ($($_.Exception.Message)). Continuing with direct interpreter path."
        }
    }

    # 3. Dependency Verification (avoid redundant reinstall on every launch)
    $reqFile = Join-Path -Path $ScriptDir -ChildPath "requirements.txt"
    $coreMarker = Join-Path -Path $venvDir -ChildPath ".requirements_installed"
    $needCoreInstall = $false

    if (-not (Test-Path -LiteralPath $coreMarker)) {
        # Check if core dependencies are already present before running pip
        & "$py" -c "import fastapi, uvicorn, networkx, rank_bm25" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $needCoreInstall = $true
        } else {
            Set-Content -LiteralPath $coreMarker -Value (Get-Date).ToString("o")
        }
    } elseif ((Test-Path -LiteralPath $reqFile) -and ((Get-Item -LiteralPath $reqFile).LastWriteTimeUtc -gt (Get-Item -LiteralPath $coreMarker).LastWriteTimeUtc)) {
        $needCoreInstall = $true
    } else {
        # Fast import sanity check
        & "$py" -c "import fastapi, uvicorn, networkx, rank_bm25" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $needCoreInstall = $true
        }
    }

    if ($needCoreInstall) {
        Write-Host "Installing/updating core dependencies from requirements.txt..." -ForegroundColor Cyan
        & "$py" -m pip install --upgrade pip | Out-Null
        & "$py" -m pip install -r "$reqFile"
        if ($LASTEXITCODE -ne 0) {
            throw "pip install -r requirements.txt failed with exit code $LASTEXITCODE."
        }
        Set-Content -LiteralPath $coreMarker -Value (Get-Date).ToString("o")
        Write-Host "Core dependencies installed successfully." -ForegroundColor Green
    }

    # 4. Optional Neural Dependencies
    if ($Neural) {
        $neuralReq = Join-Path -Path $ScriptDir -ChildPath "requirements-neural.txt"
        $neuralMarker = Join-Path -Path $venvDir -ChildPath ".requirements_neural_installed"
        $needNeuralInstall = $false

        if (-not (Test-Path -LiteralPath $neuralMarker)) {
            & "$py" -c "import torch, transformers" 2>$null
            if ($LASTEXITCODE -ne 0) {
                $needNeuralInstall = $true
            } else {
                Set-Content -LiteralPath $neuralMarker -Value (Get-Date).ToString("o")
            }
        } elseif ((Test-Path -LiteralPath $neuralReq) -and ((Get-Item -LiteralPath $neuralReq).LastWriteTimeUtc -gt (Get-Item -LiteralPath $neuralMarker).LastWriteTimeUtc)) {
            $needNeuralInstall = $true
        }

        if ($needNeuralInstall -and (Test-Path -LiteralPath $neuralReq)) {
            Write-Host "Installing neural dependencies from requirements-neural.txt..." -ForegroundColor Cyan
            & "$py" -m pip install -r "$neuralReq"
            if ($LASTEXITCODE -eq 0) {
                Set-Content -LiteralPath $neuralMarker -Value (Get-Date).ToString("o")
                Write-Host "Neural dependencies installed." -ForegroundColor Green
            } else {
                Write-Warning "Neural dependencies installation finished with exit code $LASTEXITCODE. Continuing."
            }
        }
    }

    # 5. Optional Voice Dependencies
    if ($Voice) {
        $voiceReq = Join-Path -Path $ScriptDir -ChildPath "requirements-voice.txt"
        $voiceMarker = Join-Path -Path $venvDir -ChildPath ".requirements_voice_installed"
        $needVoiceInstall = $false

        if (-not (Test-Path -LiteralPath $voiceMarker)) {
            & "$py" -c "import edge_tts" 2>$null
            if ($LASTEXITCODE -ne 0) {
                $needVoiceInstall = $true
            } else {
                Set-Content -LiteralPath $voiceMarker -Value (Get-Date).ToString("o")
            }
        } elseif ((Test-Path -LiteralPath $voiceReq) -and ((Get-Item -LiteralPath $voiceReq).LastWriteTimeUtc -gt (Get-Item -LiteralPath $voiceMarker).LastWriteTimeUtc)) {
            $needVoiceInstall = $true
        }

        if ($needVoiceInstall -and (Test-Path -LiteralPath $voiceReq)) {
            Write-Host "Installing voice dependencies from requirements-voice.txt..." -ForegroundColor Cyan
            & "$py" -m pip install -r "$voiceReq"
            if ($LASTEXITCODE -eq 0) {
                Set-Content -LiteralPath $voiceMarker -Value (Get-Date).ToString("o")
                Write-Host "Voice dependencies installed." -ForegroundColor Green
            } else {
                Write-Warning "Voice dependencies installation reported warnings or errors. Normal startup will continue."
            }
        }

        if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
            Write-Warning "ffmpeg not found on PATH -- server speech recognition will be unavailable (browser recognition still works). Install: winget install Gyan.FFmpeg"
        }
    }

    # 6. Environment configuration (.env from .env.example if missing)
    $envFile = Join-Path -Path $ScriptDir -ChildPath ".env"
    $envExample = Join-Path -Path $ScriptDir -ChildPath ".env.example"
    if (-not (Test-Path -LiteralPath $envFile) -and (Test-Path -LiteralPath $envExample)) {
        Write-Host "Initializing .env from .env.example..." -ForegroundColor Cyan
        Copy-Item -LiteralPath $envExample -Destination $envFile
    }

    # 7. Knowledge Graph v2 build if missing
    $kgFile = Join-Path -Path $ScriptDir -ChildPath "Data\processed\knowledge_graph_v2.pkl"
    if (-not (Test-Path -LiteralPath $kgFile)) {
        Write-Host "Building Knowledge Graph v2..." -ForegroundColor Cyan
        & "$py" -m app.core.kg_builder
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to build knowledge graph v2 (exit code $LASTEXITCODE)."
        }
    }

    # 8. Test mode
    if ($Test) {
        Write-Host "Running test suite..." -ForegroundColor Cyan
        & "$py" -m pytest tests -q
        exit $LASTEXITCODE
    }

    # 9. Legacy Streamlit mode
    if ($Streamlit) {
        Write-Host "Starting legacy Streamlit app..." -ForegroundColor Cyan
        $streamlitApp = Join-Path -Path $ScriptDir -ChildPath "web\app.py"
        & "$py" -m streamlit run "$streamlitApp"
        exit $LASTEXITCODE
    }

    # 10. Start AyurMitra FastAPI server
    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host " AyurMitra is starting!" -ForegroundColor Green
    Write-Host " Website:  http://127.0.0.1:$Port" -ForegroundColor Cyan
    Write-Host " API Docs: http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host ""

    & "$py" -m uvicorn api.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0) {
        throw "Uvicorn server stopped with exit code $LASTEXITCODE."
    }

} catch {
    Write-Host ""
    Write-Host "ERROR: AyurMitra startup failed!" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    exit 1
}
