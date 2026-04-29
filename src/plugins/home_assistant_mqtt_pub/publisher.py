from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PublishedRef:
    """Identifies an HA discovery topic and the payload to publish there.

    `component` is "sensor" / "binary_sensor" / "button"; `key` is the entity/command slug.
    `payload` is the dict to publish; for deletions it is replaced with an empty string.
    """
    component: str
    key: str
    payload: Any


@dataclass(frozen=True)
class PublishOp:
    topic: str
    payload: Any


@dataclass(frozen=True)
class ReconciliationPlan:
    deletions: list  # list[PublishOp]
    creations: list  # list[PublishOp]


def compute_reconciliation(*, previous, desired, current_ctx, previous_ctx) -> ReconciliationPlan:
    deletions: list[PublishOp] = []
    creations: list[PublishOp] = []

    if previous_ctx is not None and previous_ctx.device_id != current_ctx.device_id:
        for ref in previous:
            topic = previous_ctx.discovery_topic(ref.component, ref.key)
            deletions.append(PublishOp(topic=topic, payload=""))
        for ref in desired:
            topic = current_ctx.discovery_topic(ref.component, ref.key)
            creations.append(PublishOp(topic=topic, payload=ref.payload))
        return ReconciliationPlan(deletions=deletions, creations=creations)

    desired_keys = {(r.component, r.key) for r in desired}

    for ref in previous:
        if (ref.component, ref.key) not in desired_keys:
            ctx_for_delete = previous_ctx or current_ctx
            topic = ctx_for_delete.discovery_topic(ref.component, ref.key)
            deletions.append(PublishOp(topic=topic, payload=""))

    for ref in desired:
        topic = current_ctx.discovery_topic(ref.component, ref.key)
        creations.append(PublishOp(topic=topic, payload=ref.payload))

    return ReconciliationPlan(deletions=deletions, creations=creations)
