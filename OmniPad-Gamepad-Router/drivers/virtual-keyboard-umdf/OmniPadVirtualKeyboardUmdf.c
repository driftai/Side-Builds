#include "OmniPadVirtualKeyboardUmdf.h"

/*
 * Two top-level collections are exposed:
 *   Report 1: a real boot-protocol keyboard visible to Raw Input and games.
 *   Report 2: a vendor feature channel used only to submit the next key state.
 *
 * The vendor channel follows Microsoft's vhidmini2 UMDF sideband pattern.
 */
static const HID_REPORT_DESCRIPTOR g_ReportDescriptor[] = {
    /* Keyboard top-level collection, report ID 1. */
    0x05, 0x01,       /* USAGE_PAGE (Generic Desktop) */
    0x09, 0x06,       /* USAGE (Keyboard) */
    0xA1, 0x01,       /* COLLECTION (Application) */
    0x85, OMNIPAD_KEYBOARD_REPORT_ID,
    0x05, 0x07,       /*   USAGE_PAGE (Keyboard/Keypad) */
    0x19, 0xE0,
    0x29, 0xE7,
    0x15, 0x00,
    0x25, 0x01,
    0x75, 0x01,
    0x95, 0x08,
    0x81, 0x02,       /*   INPUT (Data, Variable, Absolute) */
    0x95, 0x01,
    0x75, 0x08,
    0x81, 0x01,       /*   INPUT (Constant) */
    0x95, 0x06,
    0x75, 0x08,
    0x15, 0x00,
    0x26, 0xFF, 0x00,
    0x05, 0x07,
    0x19, 0x00,
    0x29, 0xFF,
    0x81, 0x00,       /*   INPUT (Data, Array) */
    0x05, 0x08,       /*   USAGE_PAGE (LEDs) */
    0x19, 0x01,
    0x29, 0x05,
    0x95, 0x05,
    0x75, 0x01,
    0x91, 0x02,       /*   OUTPUT (Data, Variable, Absolute) */
    0x95, 0x01,
    0x75, 0x03,
    0x91, 0x01,       /*   OUTPUT (Constant) */
    0xC0,

    /* Vendor-defined control top-level collection, report ID 2. */
    0x06, 0x00, 0xFF, /* USAGE_PAGE (Vendor 0xFF00) */
    0x09, 0x01,       /* USAGE (1) */
    0xA1, 0x01,       /* COLLECTION (Application) */
    0x85, OMNIPAD_CONTROL_REPORT_ID,
    0x09, 0x01,
    0x15, 0x00,
    0x26, 0xFF, 0x00,
    0x75, 0x08,
    0x95, OMNIPAD_KEYBOARD_PAYLOAD_SIZE,
    0xB1, 0x02,       /* FEATURE (Data, Variable, Absolute) */
    0xC0
};

static const HID_DESCRIPTOR g_HidDescriptor = {
    0x09,
    0x21,
    0x0111,
    0x00,
    0x01,
    {{0x22, sizeof(g_ReportDescriptor)}}
};

static NTSTATUS OmniPadCopyToRequest(
    _In_ WDFREQUEST Request,
    _In_reads_bytes_(Length) const void *Source,
    _In_ size_t Length)
{
    WDFMEMORY memory;
    size_t outputLength = 0;
    NTSTATUS status = WdfRequestRetrieveOutputMemory(Request, &memory);

    if (!NT_SUCCESS(status)) {
        return status;
    }
    (void)WdfMemoryGetBuffer(memory, &outputLength);
    if (outputLength < Length) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    status = WdfMemoryCopyFromBuffer(memory, 0, (PVOID)Source, Length);
    if (NT_SUCCESS(status)) {
        WdfRequestSetInformation(Request, Length);
    }
    return status;
}

/* MsHidUmdf converts embedded HID_XFER_PACKET pointers into UMDF buffers. */
static NTSTATUS OmniPadGetWritePacket(
    _In_ WDFREQUEST Request,
    _Out_ HID_XFER_PACKET *Packet)
{
    WDFMEMORY inputMemory;
    WDFMEMORY outputMemory;
    size_t inputLength = 0;
    size_t outputLength = 0;
    NTSTATUS status;

    status = WdfRequestRetrieveOutputMemory(Request, &outputMemory);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    (void)WdfMemoryGetBuffer(outputMemory, &outputLength);
    Packet->reportId = (UCHAR)outputLength;

    status = WdfRequestRetrieveInputMemory(Request, &inputMemory);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    Packet->reportBuffer = (PUCHAR)WdfMemoryGetBuffer(inputMemory, &inputLength);
    Packet->reportBufferLen = (ULONG)inputLength;
    return STATUS_SUCCESS;
}

static NTSTATUS OmniPadGetReadPacket(
    _In_ WDFREQUEST Request,
    _Out_ HID_XFER_PACKET *Packet)
{
    WDFMEMORY inputMemory;
    WDFMEMORY outputMemory;
    size_t inputLength = 0;
    size_t outputLength = 0;
    PUCHAR inputBuffer;
    NTSTATUS status;

    status = WdfRequestRetrieveInputMemory(Request, &inputMemory);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    inputBuffer = (PUCHAR)WdfMemoryGetBuffer(inputMemory, &inputLength);
    if (inputLength < sizeof(UCHAR)) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    Packet->reportId = inputBuffer[0];

    status = WdfRequestRetrieveOutputMemory(Request, &outputMemory);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    Packet->reportBuffer = (PUCHAR)WdfMemoryGetBuffer(outputMemory, &outputLength);
    Packet->reportBufferLen = (ULONG)outputLength;
    return STATUS_SUCCESS;
}

static BOOLEAN OmniPadPayloadIsActive(_In_reads_(8) const UCHAR *Payload)
{
    ULONG index;
    if (Payload[0] != 0) {
        return TRUE;
    }
    for (index = 2; index < OMNIPAD_KEYBOARD_PAYLOAD_SIZE; ++index) {
        if (Payload[index] != 0) {
            return TRUE;
        }
    }
    return FALSE;
}

static void OmniPadCompletePendingRead(_In_ POMNIPAD_DEVICE_CONTEXT Context)
{
    WDFREQUEST request = NULL;
    OMNIPAD_KEYBOARD_INPUT_REPORT report;
    NTSTATUS status;

    WdfWaitLockAcquire(Context->StateLock, NULL);
    if (!Context->ReportPending) {
        WdfWaitLockRelease(Context->StateLock);
        return;
    }

    status = WdfIoQueueRetrieveNextRequest(Context->ManualQueue, &request);
    if (NT_SUCCESS(status)) {
        RtlCopyMemory(&report, &Context->LastReport, sizeof(report));
        Context->ReportPending = FALSE;
    }
    WdfWaitLockRelease(Context->StateLock);

    if (NT_SUCCESS(status)) {
        status = OmniPadCopyToRequest(request, &report, sizeof(report));
        WdfRequestComplete(request, status);
    }
}

static NTSTATUS OmniPadQueueRead(
    _In_ POMNIPAD_DEVICE_CONTEXT Context,
    _In_ WDFREQUEST Request,
    _Out_ BOOLEAN *CompleteRequest)
{
    NTSTATUS status = WdfRequestForwardToIoQueue(Request, Context->ManualQueue);
    if (!NT_SUCCESS(status)) {
        *CompleteRequest = TRUE;
        return status;
    }

    *CompleteRequest = FALSE;
    /* Recheck after queueing to close the report-arrival race. */
    OmniPadCompletePendingRead(Context);
    return STATUS_SUCCESS;
}

static NTSTATUS OmniPadSetFeature(
    _In_ POMNIPAD_DEVICE_CONTEXT Context,
    _In_ WDFREQUEST Request)
{
    HID_XFER_PACKET packet;
    POMNIPAD_CONTROL_FEATURE_REPORT control;
    BOOLEAN changed;
    NTSTATUS status = OmniPadGetWritePacket(Request, &packet);

    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != OMNIPAD_CONTROL_REPORT_ID ||
        packet.reportBufferLen < sizeof(OMNIPAD_CONTROL_FEATURE_REPORT)) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    control = (POMNIPAD_CONTROL_FEATURE_REPORT)packet.reportBuffer;
    WdfWaitLockAcquire(Context->StateLock, NULL);
    changed = (RtlCompareMemory(
        &Context->LastReport.Modifiers,
        control->Keyboard,
        OMNIPAD_KEYBOARD_PAYLOAD_SIZE) != OMNIPAD_KEYBOARD_PAYLOAD_SIZE);
    if (changed) {
        RtlCopyMemory(
            &Context->LastReport.Modifiers,
            control->Keyboard,
            OMNIPAD_KEYBOARD_PAYLOAD_SIZE);
        Context->LastReport.ReportId = OMNIPAD_KEYBOARD_REPORT_ID;
        Context->ReportPending = TRUE;
    }
    Context->KeyboardActive = OmniPadPayloadIsActive(control->Keyboard);
    Context->LastUpdateTick = GetTickCount64();
    WdfWaitLockRelease(Context->StateLock);

    WdfRequestSetInformation(Request, sizeof(OMNIPAD_CONTROL_FEATURE_REPORT));
    if (changed) {
        OmniPadCompletePendingRead(Context);
    }
    return STATUS_SUCCESS;
}

static NTSTATUS OmniPadGetFeature(
    _In_ POMNIPAD_DEVICE_CONTEXT Context,
    _In_ WDFREQUEST Request)
{
    HID_XFER_PACKET packet;
    OMNIPAD_CONTROL_FEATURE_REPORT control = {0};
    NTSTATUS status = OmniPadGetReadPacket(Request, &packet);

    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != OMNIPAD_CONTROL_REPORT_ID ||
        packet.reportBufferLen < sizeof(control)) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    control.ReportId = OMNIPAD_CONTROL_REPORT_ID;
    WdfWaitLockAcquire(Context->StateLock, NULL);
    RtlCopyMemory(
        control.Keyboard,
        &Context->LastReport.Modifiers,
        OMNIPAD_KEYBOARD_PAYLOAD_SIZE);
    WdfWaitLockRelease(Context->StateLock);
    RtlCopyMemory(packet.reportBuffer, &control, sizeof(control));
    WdfRequestSetInformation(Request, sizeof(control));
    return STATUS_SUCCESS;
}

static NTSTATUS OmniPadGetInputReport(
    _In_ POMNIPAD_DEVICE_CONTEXT Context,
    _In_ WDFREQUEST Request)
{
    HID_XFER_PACKET packet;
    OMNIPAD_KEYBOARD_INPUT_REPORT report;
    NTSTATUS status = OmniPadGetReadPacket(Request, &packet);

    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != OMNIPAD_KEYBOARD_REPORT_ID ||
        packet.reportBufferLen < sizeof(report)) {
        return STATUS_INVALID_BUFFER_SIZE;
    }

    WdfWaitLockAcquire(Context->StateLock, NULL);
    RtlCopyMemory(&report, &Context->LastReport, sizeof(report));
    WdfWaitLockRelease(Context->StateLock);
    RtlCopyMemory(packet.reportBuffer, &report, sizeof(report));
    WdfRequestSetInformation(Request, sizeof(report));
    return STATUS_SUCCESS;
}

static NTSTATUS OmniPadSetOutputReport(
    _In_ POMNIPAD_DEVICE_CONTEXT Context,
    _In_ WDFREQUEST Request)
{
    HID_XFER_PACKET packet;
    NTSTATUS status = OmniPadGetWritePacket(Request, &packet);

    if (!NT_SUCCESS(status)) {
        return status;
    }
    if (packet.reportId != OMNIPAD_KEYBOARD_REPORT_ID || packet.reportBufferLen < 2) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    Context->LedState = packet.reportBuffer[1];
    WdfRequestSetInformation(Request, 2);
    return STATUS_SUCCESS;
}

static NTSTATUS OmniPadGetStringId(
    _In_ WDFREQUEST Request,
    _Out_ ULONG *StringId)
{
    WDFMEMORY inputMemory;
    size_t inputLength = 0;
    PULONG inputValue;
    NTSTATUS status = WdfRequestRetrieveInputMemory(Request, &inputMemory);

    if (!NT_SUCCESS(status)) {
        return status;
    }
    inputValue = (PULONG)WdfMemoryGetBuffer(inputMemory, &inputLength);
    if (inputLength < sizeof(ULONG)) {
        return STATUS_INVALID_BUFFER_SIZE;
    }
    *StringId = (*inputValue & 0xFFFF);
    return STATUS_SUCCESS;
}

static NTSTATUS OmniPadGetString(_In_ WDFREQUEST Request)
{
    static const WCHAR manufacturer[] = L"DriftAI";
    static const WCHAR product[] = L"OmniPad Virtual Keyboard Port";
    static const WCHAR serial[] = L"OMNIPAD-UMDF-1";
    ULONG stringId;
    NTSTATUS status = OmniPadGetStringId(Request, &stringId);

    if (!NT_SUCCESS(status)) {
        return status;
    }
    switch (stringId) {
    case HID_STRING_ID_IMANUFACTURER:
        return OmniPadCopyToRequest(Request, manufacturer, sizeof(manufacturer));
    case HID_STRING_ID_IPRODUCT:
        return OmniPadCopyToRequest(Request, product, sizeof(product));
    case HID_STRING_ID_ISERIALNUMBER:
        return OmniPadCopyToRequest(Request, serial, sizeof(serial));
    default:
        return STATUS_INVALID_PARAMETER;
    }
}

VOID OmniPadEvtWatchdog(_In_ WDFTIMER Timer)
{
    WDFDEVICE device = (WDFDEVICE)WdfTimerGetParentObject(Timer);
    POMNIPAD_DEVICE_CONTEXT context = OmniPadGetDeviceContext(device);
    ULONGLONG now = GetTickCount64();
    BOOLEAN release = FALSE;

    WdfWaitLockAcquire(context->StateLock, NULL);
    if (context->KeyboardActive &&
        (now - context->LastUpdateTick) >= OMNIPAD_WATCHDOG_TIMEOUT_MS) {
        RtlZeroMemory(&context->LastReport.Modifiers, OMNIPAD_KEYBOARD_PAYLOAD_SIZE);
        context->LastReport.ReportId = OMNIPAD_KEYBOARD_REPORT_ID;
        context->KeyboardActive = FALSE;
        context->ReportPending = TRUE;
        release = TRUE;
    }
    WdfWaitLockRelease(context->StateLock);

    if (release) {
        OmniPadCompletePendingRead(context);
    }
}

VOID OmniPadEvtIoDeviceControl(
    _In_ WDFQUEUE Queue,
    _In_ WDFREQUEST Request,
    _In_ size_t OutputBufferLength,
    _In_ size_t InputBufferLength,
    _In_ ULONG IoControlCode)
{
    WDFDEVICE device = WdfIoQueueGetDevice(Queue);
    POMNIPAD_DEVICE_CONTEXT context = OmniPadGetDeviceContext(device);
    BOOLEAN completeRequest = TRUE;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(OutputBufferLength);
    UNREFERENCED_PARAMETER(InputBufferLength);

    switch (IoControlCode) {
    case IOCTL_HID_GET_DEVICE_DESCRIPTOR:
        status = OmniPadCopyToRequest(Request, &context->HidDescriptor, sizeof(HID_DESCRIPTOR));
        break;
    case IOCTL_HID_GET_DEVICE_ATTRIBUTES:
        status = OmniPadCopyToRequest(Request, &context->HidAttributes, sizeof(HID_DEVICE_ATTRIBUTES));
        break;
    case IOCTL_HID_GET_REPORT_DESCRIPTOR:
        status = OmniPadCopyToRequest(Request, g_ReportDescriptor, sizeof(g_ReportDescriptor));
        break;
    case IOCTL_HID_READ_REPORT:
        status = OmniPadQueueRead(context, Request, &completeRequest);
        break;
    case IOCTL_HID_WRITE_REPORT:
    case IOCTL_UMDF_HID_SET_OUTPUT_REPORT:
        status = OmniPadSetOutputReport(context, Request);
        break;
    case IOCTL_UMDF_HID_SET_FEATURE:
        status = OmniPadSetFeature(context, Request);
        break;
    case IOCTL_UMDF_HID_GET_FEATURE:
        status = OmniPadGetFeature(context, Request);
        break;
    case IOCTL_UMDF_HID_GET_INPUT_REPORT:
        status = OmniPadGetInputReport(context, Request);
        break;
    case IOCTL_HID_GET_STRING:
        status = OmniPadGetString(Request);
        break;
    case IOCTL_HID_ACTIVATE_DEVICE:
    case IOCTL_HID_DEACTIVATE_DEVICE:
    case IOCTL_HID_SEND_IDLE_NOTIFICATION_REQUEST:
        status = STATUS_SUCCESS;
        break;
    default:
        status = STATUS_NOT_IMPLEMENTED;
        break;
    }

    if (completeRequest) {
        WdfRequestComplete(Request, status);
    }
}

NTSTATUS OmniPadEvtDeviceAdd(
    _In_ WDFDRIVER Driver,
    _Inout_ PWDFDEVICE_INIT DeviceInit)
{
    WDF_OBJECT_ATTRIBUTES attributes;
    WDF_OBJECT_ATTRIBUTES childAttributes;
    WDF_IO_QUEUE_CONFIG queueConfig;
    WDF_TIMER_CONFIG timerConfig;
    WDFDEVICE device;
    POMNIPAD_DEVICE_CONTEXT context;
    NTSTATUS status;

    UNREFERENCED_PARAMETER(Driver);
    WdfFdoInitSetFilter(DeviceInit);

    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attributes, OMNIPAD_DEVICE_CONTEXT);
    status = WdfDeviceCreate(&DeviceInit, &attributes, &device);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    context = OmniPadGetDeviceContext(device);
    RtlZeroMemory(context, sizeof(*context));
    context->Device = device;
    context->HidDescriptor = g_HidDescriptor;
    context->HidAttributes.Size = sizeof(HID_DEVICE_ATTRIBUTES);
    context->HidAttributes.VendorID = OMNIPAD_UMDF_VID;
    context->HidAttributes.ProductID = OMNIPAD_UMDF_PID;
    context->HidAttributes.VersionNumber = OMNIPAD_UMDF_VERSION;
    context->LastReport.ReportId = OMNIPAD_KEYBOARD_REPORT_ID;
    context->LastUpdateTick = GetTickCount64();
    context->ReportPending = TRUE;

    WDF_OBJECT_ATTRIBUTES_INIT(&childAttributes);
    childAttributes.ParentObject = device;
    status = WdfWaitLockCreate(&childAttributes, &context->StateLock);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&queueConfig, WdfIoQueueDispatchParallel);
    queueConfig.EvtIoDeviceControl = OmniPadEvtIoDeviceControl;
    status = WdfIoQueueCreate(device, &queueConfig, WDF_NO_OBJECT_ATTRIBUTES, WDF_NO_HANDLE);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    WDF_IO_QUEUE_CONFIG_INIT(&queueConfig, WdfIoQueueDispatchManual);
    status = WdfIoQueueCreate(device, &queueConfig, WDF_NO_OBJECT_ATTRIBUTES, &context->ManualQueue);
    if (!NT_SUCCESS(status)) {
        return status;
    }

    WDF_TIMER_CONFIG_INIT_PERIODIC(&timerConfig, OmniPadEvtWatchdog, OMNIPAD_WATCHDOG_PERIOD_MS);
    WDF_OBJECT_ATTRIBUTES_INIT(&childAttributes);
    childAttributes.ParentObject = device;
    status = WdfTimerCreate(&timerConfig, &childAttributes, &context->WatchdogTimer);
    if (!NT_SUCCESS(status)) {
        return status;
    }
    WdfTimerStart(context->WatchdogTimer, WDF_REL_TIMEOUT_IN_MS(OMNIPAD_WATCHDOG_PERIOD_MS));
    return STATUS_SUCCESS;
}

NTSTATUS DriverEntry(
    _In_ PDRIVER_OBJECT DriverObject,
    _In_ PUNICODE_STRING RegistryPath)
{
    WDF_DRIVER_CONFIG config;
    WDF_DRIVER_CONFIG_INIT(&config, OmniPadEvtDeviceAdd);
    return WdfDriverCreate(
        DriverObject,
        RegistryPath,
        WDF_NO_OBJECT_ATTRIBUTES,
        &config,
        WDF_NO_HANDLE);
}
