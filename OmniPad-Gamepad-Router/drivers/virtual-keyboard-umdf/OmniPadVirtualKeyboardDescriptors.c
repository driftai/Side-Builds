#include "OmniPadVirtualKeyboardUmdf.h"

/*
 * Report 1 is a boot-protocol keyboard visible to Raw Input and games.
 * Report 2 is the private vendor feature channel used to submit key state.
 */
static const HID_REPORT_DESCRIPTOR g_ReportDescriptor[] = {
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

const HID_DESCRIPTOR *OmniPadGetHidDescriptor(void)
{
    return &g_HidDescriptor;
}

const HID_REPORT_DESCRIPTOR *OmniPadGetReportDescriptor(_Out_ size_t *Length)
{
    *Length = sizeof(g_ReportDescriptor);
    return g_ReportDescriptor;
}
