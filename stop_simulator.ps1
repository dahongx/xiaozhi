# Stop Meteo Data Simulator

# 使用当前目录作为工作目录
$WorkDir = (Get-Location).Path
$PidFile = "$WorkDir\logs\simulator.pid"

Write-Host "============================================================"
Write-Host "Meteo Data Simulator - Stop"
Write-Host "============================================================"
Write-Host ""

if (-not (Test-Path $PidFile)) {
    Write-Host "WARNING: PID file not found, simulator may not be running"
    Write-Host ""
    Write-Host "Searching for related processes..."

    $Processes = Get-WmiObject Win32_Process | Where-Object {
        $_.CommandLine -like "*meteo_data_simulator.py*"
    }

    if ($Processes) {
        Write-Host "Found processes:"
        foreach ($Proc in $Processes) {
            Write-Host "  PID: $($Proc.ProcessId) - $($Proc.CommandLine)"
        }
        Write-Host ""
        $Response = Read-Host "Stop these processes? (Y/N)"
        if ($Response -eq "Y" -or $Response -eq "y") {
            foreach ($Proc in $Processes) {
                Stop-Process -Id $Proc.ProcessId -Force
                Write-Host "Stopped process $($Proc.ProcessId)"
            }
        }
    } else {
        Write-Host "No running simulator process found"
    }
    exit
}

# Read PID
$Pid = Get-Content $PidFile

Write-Host "Stopping process (PID: $Pid)..."

try {
    $Process = Get-Process -Id $Pid -ErrorAction Stop

    if ($Process.ProcessName -eq "python") {
        Stop-Process -Id $Pid -Force
        Write-Host "SUCCESS: Simulator stopped"

        # Remove PID file
        Remove-Item $PidFile -Force
    } else {
        Write-Host "WARNING: PID $Pid is not a Python process"
    }
} catch {
    Write-Host "WARNING: Process $Pid does not exist or already stopped"
    # Remove stale PID file
    Remove-Item $PidFile -Force
}

Write-Host ""
Write-Host "============================================================"

