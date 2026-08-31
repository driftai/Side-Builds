#pragma once

#include <ntddk.h>
#include <wdf.h>
#include <vhf.h>
#include <initguid.h>
#include <guiddef.h>

#define OMNIPAD_VK_REPORT_SIZE 8
#define OMNIPAD_VK_DEVICE_NAME L"\\Device\\OmniPadVirtualKeyboard"
#define OMNIPAD_VK_SYMBOLIC_NAME L"\\DosDevices\\OmniPadVirtualKeyboard"
#define OMNIPAD_VK_DOS_NAME L"\\\\.\\OmniPadVirtualKeyboard"

// Device Interface GUID: {3F1A0F6E-7B23-4C8A-9D11-6E2B0050A14C}
DEFINE_GUID(GUID_DEVINTERFACE_OMNIPAD_VK,
    0x3f1a0f6e, 0x7b23, 0x4c8a,
    0x9d, 0x11, 0x6e, 0x2b, 0x00, 0x50, 0xa1, 0x4c);

// IOCTL: Push one complete keyboard report (state of all pressed keys).
// CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS) = 0x00222004
#define IOCTL_OMNIPAD_SET_KEYBOARD_REPORT \
    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)

// Standard HID boot-keyboard input report (8 bytes).
// [modifiers, reserved, key0, key1, key2, key3, key4, key5]
#pragma pack(push, 1)
typedef struct _OMNIPAD_KEYBOARD_REPORT {
    UCHAR Modifiers;   // bit0 LCtrl | bit1 LShift | bit2 LAlt | bit3 LGUI | bit4 RCtrl | bit5 RShift | bit6 RAlt | bit7 RGUI
    UCHAR Reserved;    // always 0
    UCHAR Keys[6];     // up to 6 simultaneous HID key usage IDs (0 = none)
} OMNIPAD_KEYBOARD_REPORT, *POMNIPAD_KEYBOARD_REPORT;
#pragma pack(pop)

typedef struct _OMNIPAD_DEVICE_CONTEXT {
    WDFDEVICE Device;
    VHFHANDLE VhfHandle;
    UCHAR LastReport[OMNIPAD_VK_REPORT_SIZE];
} OMNIPAD_DEVICE_CONTEXT, *POMNIPAD_DEVICE_CONTEXT;

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(OMNIPAD_DEVICE_CONTEXT, OmniPadGetDeviceContext);

DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD OmniPadEvtDeviceAdd;
EVT_WDF_OBJECT_CONTEXT_CLEANUP OmniPadEvtDriverCleanup;
EVT_WDF_IO_QUEUE_IO_DEVICE_CONTROL OmniPadEvtIoDeviceControl;
EVT_WDF_OBJECT_CONTEXT_CLEANUP OmniPadEvtDeviceCleanup;

NTSTATUS OmniPadCreateDevice(_Inout_ PWDFDEVICE_INIT DeviceInit);
NTSTATUS OmniPadSubmitReport(_In_ POMNIPAD_DEVICE_CONTEXT Context, _In_ const OMNIPAD_KEYBOARD_REPORT* Report);

