#include "OmniPadVirtualKeyboard.h"

// Standard HID boot keyboard report descriptor (single collection, no Report ID).
// Input report is exactly 8 bytes (1 modifier byte, 1 reserved byte, 6 key slots).
static const UCHAR g_ReportDescriptor[] = {
    0x05, 0x01,       // USAGE_PAGE (Generic Desktop)
    0x09, 0x06,       // USAGE (Keyboard)
    0xA1, 0x01,       // COLLECTION (Application)
    // Modifier byte (8 bits)
    0x05, 0x07,       //   USAGE_PAGE (Keyboard/Keypad)
    0x19, 0xE0,       //   USAGE_MINIMUM (Keyboard LeftControl)
    0x29, 0xE7,       //   USAGE_MAXIMUM (Keyboard Right GUI)
    0x15, 0x00,       //   LOGICAL_MINIMUM (0)
    0x25, 0x01,       //   LOGICAL_MAXIMUM (1)
    0x75, 0x01,       //   REPORT_SIZE (1)
    0x95, 0x08,       //   REPORT_COUNT (8)
    0x81, 0x02,       //   INPUT (Data, Variable, Absolute)
    // Reserved byte (8 bits, constant)
    0x95, 0x01,       //   REPORT_COUNT (1)
    0x75, 0x08,       //   REPORT_SIZE (8)
    0x81, 0x01,       //   INPUT (Constant)
    // Key array (6 bytes)
    0x95, 0x06,       //   REPORT_COUNT (6)
    0x75, 0x08,       //   REPORT_SIZE (8)
    0x15, 0x00,       //   LOGICAL_MINIMUM (0)
    0x25, 0x65,       //   LOGICAL_MAXIMUM (101)
    0x05, 0x07,       //   USAGE_PAGE (Keyboard/Keypad)
    0x19, 0x00,       //   USAGE_MINIMUM (0)
    0x29, 0x65,       //   USAGE_MAXIMUM (101)
    0x81, 0x00,       //   INPUT (Data, Array)
    // LEDs (5 bits output + 3 bits padding)
    0x05, 0x08,       //   USAGE_PAGE (LEDs)
    0x19, 0x01,       //   USAGE_MINIMUM (Num Lock)
    0x29, 0x05,       //   USAGE_MAXIMUM (Kana)
    0x95, 0x05,       //   REPORT_COUNT (5)
    0x75, 0x01,       //   REPORT_SIZE (1)
    0x91, 0x02,       //   OUTPUT (Data, Variable, Absolute)
    0x95, 0x01,       //   REPORT_COUNT (1)
    0x75, 0x03,       //   REPORT_SIZE (3)
    0x91, 0x01,       //   OUTPUT (Constant)
    0xC0              // END_COLLECTION
};

NTSTATUS OmniPadSubmitReport(_In_ POMNIPAD_DEVICE_CONTEXT Context,
                             _In_ const OMNIPAD_KEYBOARD_REPORT* Report)
{
    if (Context == NULL || Context->VhfHandle == NULL || Report == NULL) {
        return STATUS_DEVICE_NOT_READY;
    }

    RtlCopyMemory(Context->LastReport, Report, sizeof(OMNIPAD_KEYBOARD_REPORT));

    HID_XFER_PACKET packet;
    RtlZeroMemory(&packet, sizeof(packet));
    packet.reportBuffer = Context->LastReport;
    packet.reportBufferLen = OMNIPAD_VK_REPORT_SIZE;
    packet.reportId = 0; // No REPORT_ID in descriptor.

    return VhfReadReportSubmit(Context->VhfHandle, &packet);
}

NTSTATUS OmniPadCreateDevice(_Inout_ PWDFDEVICE_INIT DeviceInit)
{
    WDF_OBJECT_ATTRIBUTES attributes;
    WDFDEVICE device = NULL;
    WDF_IO_QUEUE_CONFIG queueConfig;
    NTSTATUS status;
    VHF_CONFIG vhfConfig;
    POMNIPAD_DEVICE_CONTEXT context;

    PAGED_CODE();

    // Name the device object so the symbolic link \\.\OmniPadVirtualKeyboard resolves.
    DECLARE_CONST_UNICODE_STRING(deviceName, OMNIPAD_VK_DEVICE_NAME);
    status = WdfDeviceInitAssignName(DeviceInit, &deviceName);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    // Grant Generic All access to BUILTIN\Users and SYSTEM so non-admin processes can open the handle.
    DECLARE_CONST_UNICODE_STRING(sddl, L"O:BAG:BAD:(A;;GA;;;BU)(A;;GA;;;SY)");
    status = WdfDeviceInitAssignSDDLString(DeviceInit, &sddl);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attributes, OMNIPAD_DEVICE_CONTEXT);
    attributes.EvtCleanupCallback = OmniPadEvtDeviceCleanup;

    status = WdfDeviceCreate(&DeviceInit, &attributes, &device);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    context = OmniPadGetDeviceContext(device);
    context->Device = device;
    context->VhfHandle = NULL;
    RtlZeroMemory(context->LastReport, sizeof(context->LastReport));

    // Create and start the virtual HID device via Microsoft Virtual HID Framework (VHF).
    VHF_CONFIG_INIT(&vhfConfig,
                    WdfDeviceWdmGetDeviceObject(device),
                    (USHORT)sizeof(g_ReportDescriptor),
                    (PUCHAR)g_ReportDescriptor);
    vhfConfig.VendorID = 0x0F0F;
    vhfConfig.ProductID = 0x0202;
    vhfConfig.VersionNumber = 0x0101;

    status = VhfCreate(&vhfConfig, &context->VhfHandle);
    if (!NT_SUCCESS(status)) {
        context->VhfHandle = NULL;
        return status;
    }

    status = VhfStart(context->VhfHandle);
    if (!NT_SUCCESS(status)) {
        VhfDelete(context->VhfHandle, TRUE);
        context->VhfHandle = NULL;
        return status;
    }

    // Expose device interface for SetupAPI enumeration.
    status = WdfDeviceCreateDeviceInterface(device, &GUID_DEVINTERFACE_OMNIPAD_VK, NULL);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    // Create symbolic link \\.\OmniPadVirtualKeyboard for direct user-mode opening.
    DECLARE_CONST_UNICODE_STRING(symLink, OMNIPAD_VK_SYMBOLIC_NAME);
    status = WdfDeviceCreateSymbolicLink(device, &symLink);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    // Sequential I/O queue for handling IOCTL requests.
    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&queueConfig, WdfIoQueueDispatchSequential);
    queueConfig.EvtIoDeviceControl = OmniPadEvtIoDeviceControl;

    status = WdfIoQueueCreate(device, &queueConfig, WDF_NO_OBJECT_ATTRIBUTES, WDF_NO_HANDLE);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    return STATUS_SUCCESS;
}

VOID OmniPadEvtIoDeviceControl(_In_ WDFQUEUE Queue,
                               _In_ WDFREQUEST Request,
                               _In_ size_t OutputBufferLength,
                               _In_ size_t InputBufferLength,
                               _In_ ULONG IoControlCode)
{
    UNREFERENCED_PARAMETER(OutputBufferLength);

    WDFDEVICE device = WdfIoQueueGetDevice(Queue);
    POMNIPAD_DEVICE_CONTEXT context = OmniPadGetDeviceContext(device);
    NTSTATUS status = STATUS_INVALID_DEVICE_REQUEST;

    if (IoControlCode == IOCTL_OMNIPAD_SET_KEYBOARD_REPORT) {
        POMNIPAD_KEYBOARD_REPORT report = NULL;
        size_t inLen = 0;
        if (InputBufferLength < OMNIPAD_VK_REPORT_SIZE) {
            WdfRequestComplete(Request, STATUS_BUFFER_TOO_SMALL);
            return;
        }

        status = WdfRequestRetrieveInputBuffer(Request, OMNIPAD_VK_REPORT_SIZE,
                                               (PVOID*)&report, &inLen);
        if (NT_SUCCESS(status)) {
            status = OmniPadSubmitReport(context, report);
        }
    }

    WdfRequestComplete(Request, status);
}

VOID OmniPadEvtDeviceCleanup(_In_ WDFOBJECT Object)
{
    POMNIPAD_DEVICE_CONTEXT context = OmniPadGetDeviceContext((WDFDEVICE)Object);
    PAGED_CODE();

    if (context != NULL && context->VhfHandle != NULL) {
        VhfDelete(context->VhfHandle, TRUE);
        context->VhfHandle = NULL;
    }
}

NTSTATUS OmniPadEvtDeviceAdd(_In_ WDFDRIVER Driver,
                             _Inout_ PWDFDEVICE_INIT DeviceInit)
{
    UNREFERENCED_PARAMETER(Driver);
    PAGED_CODE();
    return OmniPadCreateDevice(DeviceInit);
}

VOID OmniPadEvtDriverCleanup(_In_ WDFOBJECT DriverObject)
{
    UNREFERENCED_PARAMETER(DriverObject);
}

NTSTATUS DriverEntry(_In_ PDRIVER_OBJECT DriverObject,
                     _In_ PUNICODE_STRING RegistryPath)
{
    WDF_DRIVER_CONFIG config;
    WDF_OBJECT_ATTRIBUTES attributes;
    NTSTATUS status;

    WDF_DRIVER_CONFIG_INIT(&config, OmniPadEvtDeviceAdd);
    WDF_OBJECT_ATTRIBUTES_INIT(&attributes);
    attributes.EvtCleanupCallback = OmniPadEvtDriverCleanup;

    status = WdfDriverCreate(DriverObject, RegistryPath, &attributes, &config, WDF_NO_HANDLE);
    return status;
}

