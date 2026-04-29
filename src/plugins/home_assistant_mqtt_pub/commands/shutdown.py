import logging

EWX_SHUTDOWN = 0x00000001
EWX_FORCEIFHUNG = 0x00000010


class ShutdownCommand:
    key = "shutdown"
    display_name = "Shutdown"
    default_enabled = True

    def is_available(self) -> bool:
        return self._can_acquire_shutdown_privilege()

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "command_topic": ctx.command_topic(self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:power",
            "device": ctx.device_block(),
        }

    def run(self) -> None:
        try:
            self._acquire_shutdown_privilege()
            import ctypes
            ctypes.windll.user32.ExitWindowsEx(EWX_SHUTDOWN | EWX_FORCEIFHUNG, 0)
        except Exception:
            logging.exception("Shutdown failed")

    @staticmethod
    def _can_acquire_shutdown_privilege() -> bool:
        try:
            import win32security
            import win32api
            import win32con
            tok = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(),
                win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY,
            )
            luid = win32security.LookupPrivilegeValue(None, win32security.SE_SHUTDOWN_NAME)
            win32security.AdjustTokenPrivileges(
                tok, False, [(luid, win32security.SE_PRIVILEGE_ENABLED)],
            )
            return True
        except Exception:
            return False

    def _acquire_shutdown_privilege(self) -> None:
        self._can_acquire_shutdown_privilege()
