# Meteo Data Simulator - Background Startup Script
# Similar to Linux nohup command

# 使用当前目录作为工作目录
$WorkDir = (Get-Location).Path
$LogDir = "$WorkDir\logs"
$StdoutLog = "$LogDir\simulator.log"
$StderrLog = "$LogDir\simulator_err.log"
$PidFile = "$LogDir\simulator.pid"

# Create log directory
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

Write-Host "============================================================"
Write-Host "Meteo Data Simulator - Starting in Background"
Write-Host "============================================================"
Write-Host ""

# Check if already running
if (Test-Path $PidFile) {
    $OldPid = Get-Content $PidFile
    $Process = Get-Process -Id $OldPid -ErrorAction SilentlyContinue
    if ($Process -and $Process.ProcessName -eq "python") {
        Write-Host "WARNING: Simulator already running (PID: $OldPid)"
        Write-Host ""
        $Response = Read-Host "Stop old process and restart? (Y/N)"
        if ($Response -eq "Y" -or $Response -eq "y") {
            Stop-Process -Id $OldPid -Force
            Write-Host "Old process stopped"
        } else {
            Write-Host "Cancelled"
            exit
        }
    }
}

# Get Python path from current environment
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PythonPath) {
    Write-Host "ERROR: Python not found"
    Write-Host "Please activate conda environment first: conda activate xiaozhi-esp32-server"
    exit 1
}

Write-Host "Using Python: $PythonPath"
Write-Host ""

# Start process in background
$ScriptPath = "$WorkDir\main\xiaozhi-server\scripts\meteo_data_simulator.py"

# Use Start-Process to run in background
$ProcessArgs = @{
    FilePath = $PythonPath
    ArgumentList = "$ScriptPath --daemon"
    WorkingDirectory = $WorkDir
    RedirectStandardOutput = $StdoutLog
    RedirectStandardError = $StderrLog
    NoNewWindow = $true
    PassThru = $true
}

$Process = Start-Process @ProcessArgs

# Wait for process to start
Start-Sleep -Seconds 2

# Check if process is still running
$RunningProcess = Get-Process -Id $Process.Id -ErrorAction SilentlyContinue

if ($RunningProcess) {
    # Save PID
    $Process.Id | Out-File -FilePath $PidFile -Encoding ASCII

    Write-Host "SUCCESS: Simulator started in background"
    Write-Host ""
    Write-Host "Process Info:"
    Write-Host "  PID: $($Process.Id)"
    Write-Host "  Log: $StdoutLog"
    Write-Host "  Error: $StderrLog"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  View log: Get-Content $StdoutLog -Tail 20 -Wait"
    Write-Host "  Stop: .\stop_simulator.ps1"
    Write-Host "  Status: Get-Process -Id $($Process.Id)"
    Write-Host ""
    Write-Host "============================================================"
} else {
    Write-Host "ERROR: Process failed to start"
    Write-Host "Check error log: $StderrLog"
    exit 1
}

