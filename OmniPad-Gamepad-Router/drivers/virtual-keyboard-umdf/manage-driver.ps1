param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Status', 'Install', 'Remove')]
    [string]$Action,
    [switch]$Confirmed
)

$ErrorActionPreference = 'Stop'
$scriptPath = $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$hardwareId = 'Root\OmniPadVirtualKeyboardUmdf'
$certificateSubject = 'CN=OmniPad Local UMDF Development'
$packageDirectory = Join-Path $root 'x64\Debug\OmniPadVirtualKeyboardUmdf'
$catalog = Join-Path $packageDirectory 'OmniPadVirtualKeyboardUmdf.cat'

function Test-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-OmniPadDevice {
    return Get-PnpDevice -Class HIDClass -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.FriendlyName -eq 'OmniPad Virtual Keyboard Port (UMDF 2)' } |
        Where-Object {
        $ids = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction SilentlyContinue).Data
        $ids -contains $hardwareId
    } | Select-Object -First 1
}

function Get-OmniPadCertificate {
    return Get-ChildItem -LiteralPath 'Cert:\LocalMachine\My' -ErrorAction SilentlyContinue |
        Where-Object { $_.Subject -eq $certificateSubject -and $_.HasPrivateKey } |
        Sort-Object NotAfter -Descending |
        Select-Object -First 1
}

function Show-DriverStatus {
    $device = Get-OmniPadDevice
    $certificate = Get-OmniPadCertificate
    $signature = if (Test-Path -LiteralPath $catalog) {
        Get-AuthenticodeSignature -LiteralPath $catalog
    } else { $null }

    if ($device) {
        Write-Host "UMDF device: INSTALLED / $($device.Status)" -ForegroundColor Green
        Write-Host "Instance:    $($device.InstanceId)"
    } else {
        Write-Host 'UMDF device: NOT INSTALLED' -ForegroundColor Yellow
    }
    if ($certificate) {
        Write-Host "Certificate: TRUSTED LOCAL DEVELOPMENT CERTIFICATE"
        Write-Host "Thumbprint:  $($certificate.Thumbprint)"
        Write-Host "Expires:     $($certificate.NotAfter.ToString('u'))"
    } else {
        Write-Host 'Certificate: NOT PRESENT'
    }
    if ($signature) {
        Write-Host "Catalog:     $($signature.Status)"
    } else {
        Write-Host 'Catalog:     NOT BUILT'
    }
    Write-Host 'Boot mode:   unchanged by these tools'
}

function Invoke-ElevatedSelf([string]$ElevatedAction) {
    $arguments = @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        ('"' + $scriptPath + '"'),
        '-Action', $ElevatedAction, '-Confirmed'
    )
    $process = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments -Wait -PassThru
    exit $process.ExitCode
}

try {
    switch ($Action) {
    'Status' {
        Show-DriverStatus
    }
    'Install' {
        if (-not $Confirmed) {
            throw 'Install requires -Confirmed after showing the certificate and device scope.'
        }
        if (-not (Test-Administrator)) {
            Invoke-ElevatedSelf 'Install'
        }
        & (Join-Path $root 'build-driver.ps1')
        if ($LASTEXITCODE -ne 0) {
            throw "UMDF build failed with exit code $LASTEXITCODE"
        }
        & (Join-Path $root 'sign-local-package.ps1') -TrustLocalCertificate -InstallAfterSigning
        Show-DriverStatus
    }
    'Remove' {
        if (-not $Confirmed) {
            throw 'Removal requires -Confirmed after showing the exact device and certificate scope.'
        }
        if (-not (Test-Administrator)) {
            Invoke-ElevatedSelf 'Remove'
        }
        $certificate = Get-OmniPadCertificate
        $parameters = @{ RemoveDevice = $true }
        if ($certificate) {
            $parameters.CertificateThumbprint = $certificate.Thumbprint
        }
        & (Join-Path $root 'remove-driver.ps1') @parameters
        Show-DriverStatus
    }
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
