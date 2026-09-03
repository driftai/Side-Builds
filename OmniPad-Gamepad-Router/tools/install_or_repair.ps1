param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Status', 'RepairCore', 'RepairAll')]
    [string]$Action,
    [switch]$Confirmed
)

$ErrorActionPreference = 'Stop'
$scriptPath = $MyInvocation.MyCommand.Path
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
$setupScript = Join-Path $root 'tools\setup_env.bat'
$routerManager = Join-Path $root 'tools\manage_router.ps1'
$umdfManager = Join-Path $root 'drivers\virtual-keyboard-umdf\manage-driver.ps1'
$localCloudflared = Join-Path $root '.runtime\bin\cloudflared.exe'
$umdfHardwareId = 'Root\OmniPadVirtualKeyboardUmdf'

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Invoke-ElevatedSelf([string]$ElevatedAction) {
    $arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        ('"' + $scriptPath + '"'), '-Action', $ElevatedAction, '-Confirmed'
    )
    $process = Start-Process -FilePath 'powershell.exe' -Verb RunAs `
        -ArgumentList $arguments -Wait -PassThru
    exit $process.ExitCode
}

function Get-BasePython {
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ File = $python.Source; Prefix = @() }
        }
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        & $launcher.Source -3 --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return [pscustomobject]@{ File = $launcher.Source; Prefix = @('-3') }
        }
    }
    foreach ($candidate in @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\python.exe')
    )) {
        if (Test-Path -LiteralPath $candidate) {
            & $candidate --version *> $null
            if ($LASTEXITCODE -eq 0) {
                return [pscustomobject]@{ File = $candidate; Prefix = @() }
            }
        }
    }
    return $null
}

function Test-PythonEnvironment {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        return $false
    }
    & $venvPython -c 'import fastapi, uvicorn, websockets, pydantic, win32api, pynput, vgamepad' *> $null
    return $LASTEXITCODE -eq 0
}

function Get-CloudflaredPath {
    $candidates = @(
        $localCloudflared,
        (Join-Path ${env:ProgramFiles(x86)} 'cloudflared\cloudflared.exe'),
        (Join-Path $env:ProgramFiles 'cloudflared\cloudflared.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\cloudflared\cloudflared.exe')
    )
    $command = Get-Command cloudflared.exe -ErrorAction SilentlyContinue
    if ($command) {
        $candidates += $command.Source
    }
    return $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
        Select-Object -First 1
}

function Test-CloudflareBinary([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or
        $signature.SignerCertificate.Subject -notmatch 'O="?Cloudflare, Inc\.') {
        return $false
    }
    & $Path --version *> $null
    return $LASTEXITCODE -eq 0
}

function Get-UmdfDevice {
    return Get-PnpDevice -Class HIDClass -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.FriendlyName -eq 'OmniPad Virtual Keyboard Port (UMDF 2)' } |
        Where-Object {
        $ids = (Get-PnpDeviceProperty -InstanceId $_.InstanceId `
            -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction SilentlyContinue).Data
        $ids -contains $umdfHardwareId
    } | Select-Object -First 1
}

function Get-ViGEmService {
    return Get-Service -Name 'ViGEmBus' -ErrorAction SilentlyContinue
}

function Show-Readiness {
    $rows = [Collections.Generic.List[object]]::new()
    $osReady = [Environment]::OSVersion.Version.Build -ge 22000 -and [Environment]::Is64BitOperatingSystem
    $basePython = Get-BasePython
    $pythonReady = Test-PythonEnvironment
    $vigem = Get-ViGEmService
    $cloudflared = Get-CloudflaredPath
    $cloudReady = Test-CloudflareBinary $cloudflared
    $umdfPackage = Join-Path $root 'drivers\virtual-keyboard-umdf\package\x64\OmniPadVirtualKeyboardUmdf.cat'
    $umdfPackageReady = Test-Path -LiteralPath $umdfPackage
    $umdfDevice = Get-UmdfDevice
    $vhfSource = Join-Path $root 'drivers\virtual-keyboard\OmniPadVirtualKeyboard.c'

    $rows.Add([pscustomobject]@{ Component = 'Windows host'; State = $(if ($osReady) {'READY'} else {'UNSUPPORTED'}); Detail = "Build $([Environment]::OSVersion.Version.Build), $([Runtime.InteropServices.RuntimeInformation]::OSArchitecture)" })
    $rows.Add([pscustomobject]@{ Component = 'Python 3'; State = $(if ($basePython -or (Test-Path $venvPython)) {'READY'} else {'MISSING'}); Detail = $(if ($basePython) {$basePython.File} else {'repair installs user-scoped Python through winget'}) })
    $rows.Add([pscustomobject]@{ Component = 'Repo Python environment'; State = $(if ($pythonReady) {'READY'} else {'MISSING'}); Detail = $venvPython })
    $rows.Add([pscustomobject]@{ Component = 'ViGEmBus gamepad driver'; State = $(if ($vigem) {'READY'} else {'MISSING'}); Detail = $(if ($vigem) {$vigem.Status} else {'repair uses the signed MSI bundled by vgamepad'}) })
    $rows.Add([pscustomobject]@{ Component = 'Cloudflare tunnel binary'; State = $(if ($cloudReady) {'READY'} else {'MISSING'}); Detail = $(if ($cloudflared) {$cloudflared} else {'repair downloads an official signed repo-local binary'}) })
    $rows.Add([pscustomobject]@{ Component = 'Bundled UMDF package'; State = $(if ($umdfPackageReady) {'READY'} else {'MISSING'}); Detail = $umdfPackage })
    $rows.Add([pscustomobject]@{ Component = 'UMDF virtual keyboard'; State = $(if ($umdfDevice -and $umdfDevice.Status -eq 'OK') {'READY'} else {'NOT INSTALLED'}); Detail = $(if ($umdfDevice) {$umdfDevice.InstanceId} else {$umdfHardwareId}) })
    $rows.Add([pscustomobject]@{ Component = 'VHF future source'; State = $(if (Test-Path $vhfSource) {'PRESERVED'} else {'MISSING'}); Detail = 'development/Microsoft-signing path; not required at runtime' })

    Write-Host ''
    Write-Host 'OmniPad component readiness' -ForegroundColor Cyan
    $rows | Format-Table -AutoSize
    $lanReady = $pythonReady -and [bool]$vigem
    Write-Host "LAN/controller runtime: $(if ($lanReady) {'READY'} else {'REPAIR NEEDED'})"
    Write-Host "Cloudflare runtime:     $(if ($lanReady -and $cloudReady) {'READY'} else {'REPAIR NEEDED'})"
    Write-Host "Virtual keyboard:       $(if ($umdfDevice -and $umdfDevice.Status -eq 'OK') {'READY'} else {'REPAIR NEEDED'})"
    Write-Host 'Boot/Test Mode:         NOT TOUCHED by install/repair'
}

function Ensure-PythonEnvironment {
    if (-not (Test-Path -LiteralPath $venvPython)) {
        $runtime = Get-BasePython
        if (-not $runtime) {
            $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
            if (-not $winget) {
                throw 'Python 3 is missing and Windows Package Manager (winget) is unavailable.'
            }
            Write-Host 'Installing minimal user-scoped Python 3.12 through winget...' -ForegroundColor Cyan
            & $winget.Source install --id Python.Python.3.12 --exact --scope user `
                --silent --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -ne 0) {
                throw "winget Python installation failed with exit code $LASTEXITCODE"
            }
            $runtime = Get-BasePython
            if (-not $runtime) {
                throw 'Python installed, but the runtime could not be located. Open a new terminal and run repair again.'
            }
        }
        Write-Host 'Creating the repository-local Python environment...' -ForegroundColor Cyan
        & $runtime.File @($runtime.Prefix) -m venv (Join-Path $root '.venv')
        if ($LASTEXITCODE -ne 0) {
            throw "Python virtual-environment creation failed with exit code $LASTEXITCODE"
        }
    }
    & $setupScript
    if ($LASTEXITCODE -ne 0 -or -not (Test-PythonEnvironment)) {
        throw 'Repository Python dependency repair failed.'
    }
}

function Ensure-ViGEmBus {
    if (-not (Get-ViGEmService)) {
        $msi = Join-Path $root '.venv\Lib\site-packages\vgamepad\win\vigem\install\x64\ViGEmBusSetup_x64.msi'
        if (-not (Test-Path -LiteralPath $msi)) {
            throw "The vgamepad-bundled ViGEmBus installer is missing: $msi"
        }
        Write-Host 'Installing the signed ViGEmBus runtime driver...' -ForegroundColor Cyan
        $process = Start-Process -FilePath 'msiexec.exe' `
            -ArgumentList "/i `"$msi`" /qn /norestart" -Wait -PassThru
        if ($process.ExitCode -notin @(0, 3010)) {
            throw "ViGEmBus MSI failed with exit code $($process.ExitCode)"
        }
        if ($process.ExitCode -eq 3010) {
            Write-Warning 'ViGEmBus requested a reboot before it can become available.'
        }
    }
    $service = Get-ViGEmService
    if (-not $service) {
        throw 'ViGEmBus is still unavailable after installation.'
    }
    & $venvPython -c 'import vgamepad as vg; pad=vg.VX360Gamepad(); pad.reset(); pad.update(); del pad'
    if ($LASTEXITCODE -ne 0) {
        throw 'The ViGEmBus driver exists, but a real virtual Xbox controller could not be created.'
    }
}

function Ensure-LocalCloudflared {
    if (Test-CloudflareBinary $localCloudflared) {
        return
    }
    $architecture = [Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
    $asset = switch ($architecture) {
        'x64' { 'cloudflared-windows-amd64.exe' }
        'arm64' { 'cloudflared-windows-arm64.exe' }
        default { throw "No supported cloudflared runtime asset for $architecture." }
    }
    $destinationDirectory = Split-Path -Parent $localCloudflared
    New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    $download = Join-Path $destinationDirectory ($asset + '.download')
    $backup = Join-Path $destinationDirectory 'cloudflared.previous.exe'
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/$asset"
    Write-Host "Downloading official $asset into this repository's ignored runtime directory..." -ForegroundColor Cyan
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $download
    if (-not (Test-CloudflareBinary $download)) {
        throw 'Downloaded cloudflared failed its Cloudflare signature or execution check.'
    }
    if (Test-Path -LiteralPath $localCloudflared) {
        Move-Item -LiteralPath $localCloudflared -Destination $backup -Force
    }
    try {
        Move-Item -LiteralPath $download -Destination $localCloudflared -Force
        if (-not (Test-CloudflareBinary $localCloudflared)) {
            throw 'Repo-local cloudflared failed validation after placement.'
        }
        if (Test-Path -LiteralPath $backup) {
            Remove-Item -LiteralPath $backup -Force
        }
    } catch {
        if (Test-Path -LiteralPath $backup) {
            Move-Item -LiteralPath $backup -Destination $localCloudflared -Force
        }
        throw
    } finally {
        if (Test-Path -LiteralPath $download) {
            Remove-Item -LiteralPath $download -Force
        }
    }
}

function Invoke-Repair([bool]$IncludeUmdf) {
    if (-not $Confirmed) {
        throw 'Repair requires -Confirmed after the exact scope is shown by install_or_repair.bat.'
    }
    $requiresAdministrator = $IncludeUmdf -or -not (Get-ViGEmService)
    if ($requiresAdministrator -and -not (Test-Administrator)) {
        Invoke-ElevatedSelf $(if ($IncludeUmdf) {'RepairAll'} else {'RepairCore'})
    }
    if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture -ne 'X64') {
        throw 'The current bundled ViGEmBus and OmniPad driver packages require x64 Windows.'
    }
    Write-Host 'Stopping only this repository router before dependency repair...' -ForegroundColor Cyan
    & $routerManager -Action Stop
    if (-not $?) {
        throw 'Could not stop the scoped OmniPad router cleanly.'
    }
    Ensure-PythonEnvironment
    Ensure-ViGEmBus
    Ensure-LocalCloudflared
    if ($IncludeUmdf) {
        & $umdfManager -Action Install -Confirmed
        if (-not $?) {
            throw 'UMDF keyboard install/repair failed.'
        }
    }
    Write-Host ''
    Write-Host 'Install/repair completed. The router remains stopped until you start it.' -ForegroundColor Green
    Show-Readiness
}

try {
    switch ($Action) {
        'Status' { Show-Readiness }
        'RepairCore' { Invoke-Repair $false }
        'RepairAll' { Invoke-Repair $true }
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
