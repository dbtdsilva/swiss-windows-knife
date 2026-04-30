from unittest.mock import MagicMock, patch

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.disk_free import (
    DiskFreeEntity,
    discover_disk_free_entities,
)


def test_discover_yields_entity_per_fixed_partition():
    fake_partitions = [
        MagicMock(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed"),
        MagicMock(device="D:\\", mountpoint="D:\\", fstype="NTFS", opts="rw,fixed"),
        MagicMock(device="E:\\", mountpoint="E:\\", fstype="UDF", opts="ro,cdrom"),
    ]
    with patch("psutil.disk_partitions", return_value=fake_partitions):
        entities = discover_disk_free_entities()
    keys = [e.key for e in entities]
    assert "disk_free_c" in keys
    assert "disk_free_d" in keys
    assert "disk_free_e" not in keys  # CD-ROM excluded


def test_sample_converts_bytes_to_gb():
    e = DiskFreeEntity(drive_letter="c", mountpoint="C:\\")
    fake = MagicMock(free=200 * 1024 ** 3)
    with patch("psutil.disk_usage", return_value=fake):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 200.0
    assert result.unit == "GB"


def test_default_interval_300s():
    assert DiskFreeEntity(drive_letter="c", mountpoint="C:\\").default_interval_s == 300
