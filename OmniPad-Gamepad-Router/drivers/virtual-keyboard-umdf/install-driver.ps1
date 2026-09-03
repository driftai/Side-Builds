param(
    [string]$InfPath = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$hardwareId = 'Root\OmniPadVirtualKeyboardUmdf'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this installer from an elevated PowerShell window.'
}

if ([Environment]::OSVersion.Version.Build -lt 22000) {
    throw 'The UMDF HID path requires Windows 11 build 22000 or newer (MsHidUmdf.inf).'
}

if (-not $InfPath) {
    $candidate = Get-ChildItem -LiteralPath $root -Recurse -Filter 'OmniPadVirtualKeyboardUmdf.inf' -File |
        Where-Object { $_.FullName -match '\\x64\\Debug\\OmniPadVirtualKeyboardUmdf\\' } |
        Select-Object -First 1
    if (-not $candidate) {
        throw 'Packaged INF not found. Run build-driver.ps1 first.'
    }
    $InfPath = $candidate.FullName
}

$InfPath = (Resolve-Path -LiteralPath $InfPath).Path
$packageDirectory = Split-Path -Parent $InfPath
$catalog = Join-Path $packageDirectory 'OmniPadVirtualKeyboardUmdf.cat'
if (-not (Test-Path -LiteralPath $catalog)) {
    throw "Catalog not found: $catalog"
}
$signature = Get-AuthenticodeSignature -LiteralPath $catalog
if ($signature.Status -ne 'Valid') {
    throw "The catalog signature is not trusted ($($signature.Status)). Sign the package before installation."
}

function Get-OmniPadDevice {
    return Get-PnpDevice -Class HIDClass -ErrorAction SilentlyContinue |
    Where-Object { $_.FriendlyName -eq 'OmniPad Virtual Keyboard Port (UMDF 2)' } |
    Where-Object {
    $ids = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_HardwareIds' -ErrorAction SilentlyContinue).Data
    $ids -contains $hardwareId
} | Select-Object -First 1
}

if (-not ('OmniPadRootDeviceInstaller' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;

public static class OmniPadRootDeviceInstaller
{
    private const uint DICD_GENERATE_ID = 0x00000001;
    private const uint SPDRP_HARDWAREID = 0x00000001;
    private const uint DIF_REGISTERDEVICE = 0x00000019;
    private static readonly IntPtr INVALID_HANDLE_VALUE = new IntPtr(-1);

    [StructLayout(LayoutKind.Sequential)]
    private struct SP_DEVINFO_DATA
    {
        public int cbSize;
        public Guid ClassGuid;
        public uint DevInst;
        public IntPtr Reserved;
    }

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool SetupDiGetINFClass(
        string infName, out Guid classGuid, StringBuilder className,
        uint classNameSize, out uint requiredSize);

    [DllImport("setupapi.dll", SetLastError = true)]
    private static extern IntPtr SetupDiCreateDeviceInfoList(ref Guid classGuid, IntPtr parent);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool SetupDiCreateDeviceInfo(
        IntPtr set, string deviceName, ref Guid classGuid, string description,
        IntPtr parent, uint creationFlags, ref SP_DEVINFO_DATA deviceInfo);

    [DllImport("setupapi.dll", SetLastError = true)]
    private static extern bool SetupDiSetDeviceRegistryProperty(
        IntPtr set, ref SP_DEVINFO_DATA deviceInfo, uint property,
        byte[] buffer, uint bufferSize);

    [DllImport("setupapi.dll", SetLastError = true)]
    private static extern bool SetupDiCallClassInstaller(
        uint installFunction, IntPtr set, ref SP_DEVINFO_DATA deviceInfo);

    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool SetupDiGetDeviceInstanceId(
        IntPtr set, ref SP_DEVINFO_DATA deviceInfo, StringBuilder instanceId,
        uint instanceIdSize, out uint requiredSize);

    [DllImport("setupapi.dll", SetLastError = true)]
    private static extern bool SetupDiDestroyDeviceInfoList(IntPtr set);

    private static void Require(bool result, string operation)
    {
        if (!result) throw new Win32Exception(Marshal.GetLastWin32Error(), operation);
    }

    public static string Create(string infPath, string hardwareId)
    {
        Guid classGuid;
        uint required;
        var className = new StringBuilder(256);
        Require(SetupDiGetINFClass(infPath, out classGuid, className, 256, out required),
            "SetupDiGetINFClass failed");
        IntPtr set = SetupDiCreateDeviceInfoList(ref classGuid, IntPtr.Zero);
        if (set == INVALID_HANDLE_VALUE)
            throw new Win32Exception(Marshal.GetLastWin32Error(), "SetupDiCreateDeviceInfoList failed");
        try
        {
            var deviceInfo = new SP_DEVINFO_DATA();
            deviceInfo.cbSize = Marshal.SizeOf(typeof(SP_DEVINFO_DATA));
            Require(SetupDiCreateDeviceInfo(set, className.ToString(), ref classGuid, null,
                IntPtr.Zero, DICD_GENERATE_ID, ref deviceInfo), "SetupDiCreateDeviceInfo failed");
            byte[] hardwareIds = Encoding.Unicode.GetBytes(hardwareId + "\0\0");
            Require(SetupDiSetDeviceRegistryProperty(set, ref deviceInfo, SPDRP_HARDWAREID,
                hardwareIds, (uint)hardwareIds.Length), "Setting the scoped hardware ID failed");
            Require(SetupDiCallClassInstaller(DIF_REGISTERDEVICE, set, ref deviceInfo),
                "Registering the scoped root device failed");
            var instanceId = new StringBuilder(512);
            Require(SetupDiGetDeviceInstanceId(set, ref deviceInfo, instanceId, 512, out required),
                "Reading the new device instance ID failed");
            return instanceId.ToString();
        }
        finally
        {
            SetupDiDestroyDeviceInfoList(set);
        }
    }
}
'@
}

Write-Host 'Installing the signed UMDF package without changing boot mode...' -ForegroundColor Cyan
$installedDevice = Get-OmniPadDevice
$createdInstance = $null
if ($installedDevice) {
    Write-Host "Updating existing device $($installedDevice.InstanceId)..." -ForegroundColor Cyan
} else {
    Write-Host "Creating only the root device $hardwareId through Windows SetupAPI..." -ForegroundColor Cyan
    $createdInstance = [OmniPadRootDeviceInstaller]::Create($InfPath, $hardwareId)
}
try {
    & pnputil.exe /add-driver $InfPath /install
    $pnpInstallExit = $LASTEXITCODE
    # PnPUtil returns ERROR_NO_MORE_ITEMS (259) when the exact package and
    # device are already current. Never trust that code alone: the scoped
    # post-install device/status check below still has to pass.
    if ($pnpInstallExit -notin @(0, 259)) {
        throw "PnPUtil installation failed with exit code $pnpInstallExit"
    }
    & pnputil.exe /scan-devices | Out-Null
    $ready = $null
    for ($attempt = 0; $attempt -lt 50; $attempt++) {
        $ready = Get-OmniPadDevice
        if ($ready -and $ready.Status -eq 'OK') {
            break
        }
        Start-Sleep -Milliseconds 100
    }
    if (-not $ready -or $ready.Status -ne 'OK') {
        throw 'The UMDF package was staged, but the exact OmniPad device did not become ready.'
    }
} catch {
    if ($createdInstance) {
        Write-Warning "Rolling back newly-created device $createdInstance after installation failure."
        & pnputil.exe /remove-device $createdInstance | Out-Null
    }
    throw
}
Write-Host "OmniPad Virtual Keyboard Port ready at $($ready.InstanceId)." -ForegroundColor Green
Write-Host 'No Test Mode, BCD, Secure Boot, SDK, WDK, DevCon, or reboot change was made.' -ForegroundColor Green
