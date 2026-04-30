from swiss_windows_knife.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from swiss_windows_knife.plugins.home_assistant_mqtt_pub.publisher import (
    PublishedRef,
    compute_reconciliation,
)


def test_first_run_publishes_all_desired():
    ctx = DeviceContext(name="pc")
    desired = [
        PublishedRef(component="sensor", key="cpu_usage", payload={"name": "CPU"}),
        PublishedRef(component="button", key="lock", payload={"name": "Lock"}),
    ]
    plan = compute_reconciliation(previous=[], desired=desired, current_ctx=ctx, previous_ctx=None)
    assert len(plan.deletions) == 0
    expected_cpu = ("homeassistant/sensor/swk_pc/cpu_usage/config", {"name": "CPU"})
    expected_lock = ("homeassistant/button/swk_pc/lock/config", {"name": "Lock"})
    creates_serializable = set()
    for op in plan.creations:
        creates_serializable.add((op.topic, frozenset(op.payload.items())))
    assert (expected_cpu[0], frozenset(expected_cpu[1].items())) in creates_serializable
    assert (expected_lock[0], frozenset(expected_lock[1].items())) in creates_serializable


def test_disabled_entity_gets_empty_payload_deletion():
    ctx = DeviceContext(name="pc")
    previous = [PublishedRef(component="sensor", key="cpu_usage", payload={})]
    desired: list[PublishedRef] = []
    plan = compute_reconciliation(previous=previous, desired=desired, current_ctx=ctx, previous_ctx=ctx)
    deletions = [(p.topic, p.payload) for p in plan.deletions]
    assert deletions == [("homeassistant/sensor/swk_pc/cpu_usage/config", "")]


def test_enabling_new_entity_creates_full_payload():
    ctx = DeviceContext(name="pc")
    previous = [PublishedRef(component="sensor", key="cpu_usage", payload={})]
    desired = [
        PublishedRef(component="sensor", key="cpu_usage", payload={"name": "CPU"}),
        PublishedRef(component="sensor", key="memory_usage", payload={"name": "Mem"}),
    ]
    plan = compute_reconciliation(previous=previous, desired=desired, current_ctx=ctx, previous_ctx=ctx)
    assert plan.deletions == []
    creates = {(p.topic, p.payload["name"]) for p in plan.creations}
    assert ("homeassistant/sensor/swk_pc/memory_usage/config", "Mem") in creates


def test_no_op_for_unchanged_entities():
    ctx = DeviceContext(name="pc")
    previous = [PublishedRef(component="sensor", key="cpu_usage", payload={})]
    desired = [PublishedRef(component="sensor", key="cpu_usage", payload={"name": "CPU"})]
    plan = compute_reconciliation(previous=previous, desired=desired, current_ctx=ctx, previous_ctx=ctx)
    # We re-publish discovery for kept entities (cheap, idempotent, covers payload changes).
    creates = [p.topic for p in plan.creations]
    assert "homeassistant/sensor/swk_pc/cpu_usage/config" in creates
    assert plan.deletions == []


def test_device_rename_deletes_all_old_topics_then_creates_new():
    old = DeviceContext(name="OldPC")
    new = DeviceContext(name="NewPC")
    previous = [
        PublishedRef(component="sensor", key="cpu_usage", payload={}),
        PublishedRef(component="button", key="lock", payload={}),
    ]
    desired = [
        PublishedRef(component="sensor", key="cpu_usage", payload={"name": "CPU"}),
        PublishedRef(component="button", key="lock", payload={"name": "Lock"}),
    ]
    plan = compute_reconciliation(previous=previous, desired=desired, current_ctx=new, previous_ctx=old)
    deletions = {p.topic for p in plan.deletions}
    assert "homeassistant/sensor/swk_oldpc/cpu_usage/config" in deletions
    assert "homeassistant/button/swk_oldpc/lock/config" in deletions
    creates = {p.topic for p in plan.creations}
    assert "homeassistant/sensor/swk_newpc/cpu_usage/config" in creates
    assert "homeassistant/button/swk_newpc/lock/config" in creates
