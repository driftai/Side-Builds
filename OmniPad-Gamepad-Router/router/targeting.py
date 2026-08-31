"""Running-application discovery and target locking for Windows.

This module deliberately avoids process injection. A target is metadata + a foreground
window guard used to decide when keyboard-compatibility injection is allowed.
"""

from __future__ import annotations

import ctypes
import logging
import os
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("OmniPad.Targeting")

IS_WINDOWS = os.name == "nt"
if IS_WINDOWS:
    import win32api  # type: ignore
    import win32con  # type: ignore
    import win32gui  # type: ignore
    import win32process  # type: ignore
else:  # pragma: no cover
    win32api = win32con = win32gui = win32process = None


@dataclass
class WindowTarget:
    hwnd: int
    pid: int
    title: str
    process_name: str
    exe_path: Optional[str]
    is_visible: bool = True
    selected: bool = False

    @property
    def label(self) -> str:
        exe = self.process_name or "unknown"
        return f"{self.title} — {exe} (PID {self.pid})" if self.title else f"{exe} (PID {self.pid})"

    def public_dict(self) -> Dict[str, Any]:
        return {**asdict(self), "label": self.label}


class TargetManager:
    """Enumerates top-level windows and maintains an optional selected target."""

    def __init__(self) -> None:
        self.selected: Optional[WindowTarget] = None
        self.selected_at: Optional[float] = None
        self.selection_mode: str = "target-process"

    def list_windows(self, include_empty_titles: bool = False) -> List[WindowTarget]:
        if not IS_WINDOWS:
            return []

        result: List[WindowTarget] = []

        def enum_proc(hwnd: int, _lparam: int) -> None:
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return
                title = win32gui.GetWindowText(hwnd).strip()
                if not title and not include_empty_titles:
                    return
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process_name = ""
                exe_path: Optional[str] = None
                handle = None
                try:
                    handle = win32api.OpenProcess(
                        win32con.PROCESS_QUERY_LIMITED_INFORMATION,
                        False,
                        pid,
                    )
                    if handle:
                        exe_path = win32process.GetModuleFileNameEx(handle, 0)
                        if not exe_path:
                            exe_path_buf = ctypes.create_unicode_buffer(32768)
                            size = ctypes.c_ulong(len(exe_path_buf))
                            ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
                                int(handle), 0, exe_path_buf, ctypes.byref(size)
                            )
                            if ok:
                                exe_path = exe_path_buf.value
                        process_name = os.path.basename(exe_path) if exe_path else ""
                except Exception:
                    process_name = ""
                finally:
                    try:
                        if handle:
                            win32api.CloseHandle(handle)
                    except Exception:
                        pass

                selected = bool(self.selected and self.selected.hwnd == hwnd and self.selected.pid == pid)
                result.append(WindowTarget(hwnd, pid, title, process_name, exe_path, True, selected))
            except Exception as exc:
                logger.debug("Window enumeration error for %s: %s", hwnd, exc)

        try:
            win32gui.EnumWindows(enum_proc, 0)
        except Exception as exc:
            logger.debug("EnumWindows call failed: %s", exc)
        result.sort(key=lambda x: (not x.selected, x.title.lower(), x.pid))
        return result

    def select(self, hwnd: Optional[int] = None, pid: Optional[int] = None) -> Optional[WindowTarget]:
        if not IS_WINDOWS:
            return None
        candidates = self.list_windows(include_empty_titles=True)
        picked = None
        for item in candidates:
            if hwnd is not None and item.hwnd == int(hwnd):
                picked = item
                break
            if hwnd is None and pid is not None and item.pid == int(pid):
                if picked is None or (not picked.title and item.title):
                    picked = item
        if picked is None:
            return None
        picked.selected = True
        self.selected = picked
        self.selected_at = time.time()
        logger.info("Selected target: %s", picked.label)
        return picked

    def clear(self) -> None:
        logger.info("Cleared target selection")
        self.selected = None
        self.selected_at = None

    def refresh_selection(self) -> Optional[WindowTarget]:
        if not self.selected:
            return None
        refreshed = self.select(hwnd=self.selected.hwnd)
        if refreshed is None:
            self.clear()
            return None
        return refreshed

    def foreground(self) -> Optional[WindowTarget]:
        if not IS_WINDOWS:
            return None
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            title = win32gui.GetWindowText(hwnd).strip()
            process_name = ""
            exe_path = None
            handle = None
            try:
                handle = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_LIMITED_INFORMATION,
                    False,
                    pid,
                )
                if handle:
                    exe_path = win32process.GetModuleFileNameEx(handle, 0) or None
                    process_name = os.path.basename(exe_path) if exe_path else ""
            except Exception:
                pass
            finally:
                try:
                    if handle:
                        win32api.CloseHandle(handle)
                except Exception:
                    pass
            return WindowTarget(hwnd, pid, title, process_name, exe_path)
        except Exception:
            return None

    def is_target_foreground(self) -> bool:
        if not self.selected:
            return True
        fg = self.foreground()
        if not fg:
            return False
        return fg.pid == self.selected.pid or fg.hwnd == self.selected.hwnd

    def is_target_running(self) -> bool:
        """Return True while the selected target process still owns a window.

        This intentionally ignores foreground focus so virtual controller outputs
        can keep reaching the selected game's input device while a screen-share,
        stream, dashboard, or other host window is on top.
        """
        if not self.selected:
            return True
        if not IS_WINDOWS:
            return False
        try:
            targets = self.list_windows(include_empty_titles=True)
            return any(item.pid == self.selected.pid and win32gui.IsWindow(item.hwnd) for item in targets)
        except Exception:
            return False

    def get_status(self) -> Dict[str, Any]:
        fg = self.foreground()
        return {
            "selected": self.selected.public_dict() if self.selected else None,
            "selected_at": self.selected_at,
            "foreground": fg.public_dict() if fg else None,
            "target_foreground": self.is_target_foreground() if self.selected else None,
            "target_running": self.is_target_running() if self.selected else None,
            "selection_mode": self.selection_mode,
            "platform_windows": IS_WINDOWS,
        }


# Singleton shared by REST handlers and controller backends.
target_manager = TargetManager()
