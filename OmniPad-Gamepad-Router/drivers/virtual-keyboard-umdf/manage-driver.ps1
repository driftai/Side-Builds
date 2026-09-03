param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Status', 'Install', 'RebuildInstall', 'Remove')]
    [string]$Action,
    [switch]$Confirmed
)

$ErrorActionPreference = 'Stop'
$scriptPath = $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$hardwareId = 'Root\OmniPadVirtualKeyboardUmdf'
$certificateSubject = 'CN=OmniPad Local UMDF Development'
$packageDirectory = Join-Path $root 'package\x64'
$catalog = Join-Path $packageDirectory 'OmniPadVirtualKeyboardUmdf.cat'
$bundledThumbprint = '5631FB22CE4E3E6512CAADE65B4F5963644BB56D'

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

function Get-OmniPadCertificates {
    $certificates = foreach ($store in @('My', 'Root', 'TrustedPublisher')) {
        Get-ChildItem -LiteralPath "Cert:\LocalMachine\$store" -ErrorAction SilentlyContinue |
            Where-Object { $_.Subject -eq $certificateSubject } |
            ForEach-Object { [pscustomobject]@{ Store = $store; Certificate = $_ } }
    }
    return @($certificates)
}

function Show-DriverStatus {
    $device = Get-OmniPadDevice
    $certificates = @(Get-OmniPadCertificates)
    $signature = if (Test-Path -LiteralPath $catalog) {
        Get-AuthenticodeSignature -LiteralPath $catalog
    } else { $null }

    if ($device) {
        Write-Host "UMDF device: INSTALLED / $($device.Status)" -ForegroundColor Green
        Write-Host "Instance:    $($device.InstanceId)"
    } else {
        Write-Host 'UMDF device: NOT INSTALLED' -ForegroundColor Yellow
    }
    $trusted = @($certificates | Where-Object {
        $_.Store -in @('Root', 'TrustedPublisher') -and
        $_.Certificate.Thumbprint -eq $bundledThumbprint
    })
    if ($trusted.Count -gt 0) {
        Write-Host 'Certificate: PINNED BUNDLED SIGNER TRUSTED'
        Write-Host "Thumbprint:  $bundledThumbprint"
        Write-Host "Stores:      $($trusted.Store -join ', ')"
    } else {
        Write-Host 'Certificate: BUNDLED SIGNER NOT TRUSTED'
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
        & (Join-Path $root 'install-bundled-package.ps1') -TrustBundledCertificate
        if (-not $?) {
            throw 'Bundled UMDF installation failed.'
        }
        Show-DriverStatus
    }
    'RebuildInstall' {
        if (-not $Confirmed) {
            throw 'Developer rebuild/install requires -Confirmed after showing the certificate and device scope.'
        }
        if (-not (Test-Administrator)) {
            Invoke-ElevatedSelf 'RebuildInstall'
        }
        & (Join-Path $root 'build-driver.ps1')
        if (-not $?) {
            throw 'UMDF build failed.'
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
        $certificates = @(Get-OmniPadCertificates)
        $parameters = @{ RemoveDevice = $true }
        if ($certificates.Count -gt 0) {
            $parameters.CertificateThumbprint = @(
                $certificates.Certificate.Thumbprint | Sort-Object -Unique
            )
        }
        & (Join-Path $root 'remove-driver.ps1') @parameters
        Show-DriverStatus
    }
    }
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
