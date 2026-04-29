import logging

import psutil

from .base import SampleResult


class DiskFreeEntity:
    component = "sensor"
    default_enabled = True
    default_interval_s = 300
    is_event_driven = False

    def __init__(self, drive_letter: str, mountpoint: str) -> None:
        self.drive_letter = drive_letter.lower()
        self.mountpoint = mountpoint
        self.key = f"disk_free_{self.drive_letter}"
        self.display_name = f"Free space {drive_letter.upper()}:"

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "GB",
            "icon": "mdi:harddisk",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            usage = psutil.disk_usage(self.mountpoint)
        except Exception as exc:
            logging.debug("disk_free failed for %s: %s", self.mountpoint, exc)
            return SampleResult.unavailable(reason=str(exc))
        gb = round(usage.free / (1024 ** 3), 1)
        return SampleResult.available(value=gb, unit="GB")


def discover_disk_free_entities() -> list[DiskFreeEntity]:
    out: list[DiskFreeEntity] = []
    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception:
        return out
    for p in partitions:
        opts = (p.opts or "").lower()
        # Skip CD-ROM, removable, and other non-fixed media.
        if "cdrom" in opts or "removable" in opts:
            continue
        # Mountpoint like "C:\\" — first character is drive letter.
        mp = p.mountpoint
        if len(mp) < 2 or mp[1] != ":":
            continue
        out.append(DiskFreeEntity(drive_letter=mp[0], mountpoint=mp))
    return out
