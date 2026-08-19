import ctypes
import os
from ctypes import wintypes


IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    GA_ROOT = 2

    class GUITHREADINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("hwndActive", wintypes.HWND),
            ("hwndFocus", wintypes.HWND),
            ("hwndCapture", wintypes.HWND),
            ("hwndMenuOwner", wintypes.HWND),
            ("hwndMoveSize", wintypes.HWND),
            ("hwndCaret", wintypes.HWND),
            ("rcCaret", wintypes.RECT),
        ]

    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetGUIThreadInfo.argtypes = (wintypes.DWORD, ctypes.POINTER(GUITHREADINFO))
    user32.GetGUIThreadInfo.restype = wintypes.BOOL
    user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.restype = ctypes.c_int


def list_windows() -> list[dict[str, object]]:
    if not IS_WINDOWS:
        return []
    results: list[dict[str, object]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        title = window_title(hwnd)
        if title:
            results.append({"hwnd": int(hwnd), "title": title})
        return True

    user32.EnumWindows(callback_type(callback), 0)
    return sorted(results, key=lambda item: str(item["title"]).lower())


def window_title(hwnd: int) -> str:
    if not IS_WINDOWS or not hwnd:
        return ""
    handle = wintypes.HWND(int(hwnd))
    if not user32.IsWindow(handle):
        return ""
    length = user32.GetWindowTextLengthW(handle)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    return buffer.value.strip()


def window_class(hwnd: int) -> str:
    if not IS_WINDOWS or not hwnd:
        return ""
    buffer = ctypes.create_unicode_buffer(256)
    count = user32.GetClassNameW(wintypes.HWND(int(hwnd)), buffer, len(buffer))
    return buffer.value[:count] if count else ""


def window_thread(hwnd: int) -> tuple[int, int]:
    if not IS_WINDOWS or not hwnd:
        return 0, 0
    process_id = wintypes.DWORD(0)
    thread_id = int(user32.GetWindowThreadProcessId(wintypes.HWND(int(hwnd)), ctypes.byref(process_id)))
    return thread_id, int(process_id.value)


def _root(hwnd: int) -> int:
    if not IS_WINDOWS or not hwnd:
        return 0
    return int(user32.GetAncestor(wintypes.HWND(int(hwnd)), GA_ROOT) or 0)


def background_target_info(hwnd: int) -> dict[str, object]:
    """Resolve the selected top-level HWND to its retained keyboard-focus recipient."""
    if not IS_WINDOWS or not hwnd:
        return {"target_hwnd": 0, "recipient_hwnd": 0, "thread_id": 0, "process_id": 0, "source": "none", "class_name": ""}
    target = int(hwnd)
    thread_id, process_id = window_thread(target)
    focus = active = 0
    if thread_id:
        info = GUITHREADINFO(cbSize=ctypes.sizeof(GUITHREADINFO))
        if user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
            focus = int(info.hwndFocus or 0)
            active = int(info.hwndActive or 0)

    target_root = _root(target) or target
    recipient = target
    source = "top-level"
    for candidate, label in ((focus, "thread-focus"), (active, "thread-active")):
        if candidate and user32.IsWindow(wintypes.HWND(candidate)) and (_root(candidate) or candidate) == target_root:
            recipient = candidate
            source = label
            break
    return {
        "target_hwnd": target,
        "recipient_hwnd": recipient,
        "thread_id": thread_id,
        "process_id": process_id,
        "source": source,
        "class_name": window_class(recipient),
        "title": window_title(target),
    }


def resolve_window(title_contains: str, hwnd: int = 0) -> tuple[int, str]:
    if not IS_WINDOWS:
        return 0, "Window targeting is only available on Windows."
    if hwnd:
        title = window_title(hwnd)
        if title:
            return int(hwnd), title
    query = title_contains.strip().lower()
    if not query:
        return 0, "No target window was selected."
    matches = [w for w in list_windows() if query in str(w["title"]).lower()]
    if not matches:
        return 0, f"No visible window contains: {title_contains}"
    return int(matches[0]["hwnd"]), str(matches[0]["title"])


def focus_window(title_contains: str, hwnd: int = 0) -> tuple[bool, str]:
    if not IS_WINDOWS:
        return False, "Window focus is only available on Windows."
    target, title = resolve_window(title_contains, hwnd)
    if not target:
        return False, title
    user32.ShowWindow(wintypes.HWND(target), 9)  # SW_RESTORE
    ok = bool(user32.SetForegroundWindow(wintypes.HWND(target)))
    return ok, title
