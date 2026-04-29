import json
import logging
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QTimer

from .entities.base import SampleResult


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


def _serialize(value) -> str:
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


class Publisher:
    def __init__(self, session, ctx, settings, sampler, entities, commands) -> None:
        self._session = session
        self._ctx = ctx
        self._settings = settings
        self._sampler = sampler
        self._entities = list(entities)
        self._commands = list(commands)
        self._timers: dict[str, QTimer] = {}

    def _enabled_entities(self) -> list:
        return [e for e in self._entities
                if self._settings.is_publish_enabled(e.key, e.default_enabled)]

    def _enabled_commands(self) -> list:
        return [c for c in self._commands
                if self._settings.is_command_enabled(c.key, c.default_enabled)]

    def _desired_refs(self) -> list:
        refs = []
        for e in self._enabled_entities():
            refs.append(PublishedRef(component=e.component, key=e.key, payload=e.discovery_payload(self._ctx)))
        for c in self._enabled_commands():
            refs.append(PublishedRef(component="button", key=c.key, payload=c.discovery_payload(self._ctx)))
        return refs

    def _previous_refs(self) -> list:
        if self._settings.previous_device_name() is None:
            return []
        refs = []
        for e in self._entities:
            refs.append(PublishedRef(component=e.component, key=e.key, payload={}))
        for c in self._commands:
            refs.append(PublishedRef(component="button", key=c.key, payload={}))
        return refs

    def _previous_ctx(self):
        prev = self._settings.previous_device_name()
        if prev is None:
            return None
        from .device_context import DeviceContext
        return DeviceContext(name=prev)

    def on_connected(self) -> None:
        self.apply()
        self._session.publish(self._ctx.availability_topic, "online", retain=True)
        for entity in self._enabled_entities():
            self.tick(entity)
        self._restart_timers()
        for entity in self._entities:
            if entity.is_event_driven and self._settings.is_publish_enabled(entity.key, entity.default_enabled):
                entity.subscribe(lambda result, e=entity: self._publish_state(e, result))

    def apply(self) -> None:
        plan = compute_reconciliation(
            previous=self._previous_refs(),
            desired=self._desired_refs(),
            current_ctx=self._ctx,
            previous_ctx=self._previous_ctx(),
        )
        for op in plan.deletions:
            self._session.publish(op.topic, op.payload, retain=True)
        for op in plan.creations:
            payload = json.dumps(op.payload) if isinstance(op.payload, dict) else op.payload
            self._session.publish(op.topic, payload, retain=True)
        self._settings.set_previous_device_name(self._ctx.name)
        self._restart_timers()

    def tick(self, entity) -> None:
        self._sampler.submit(entity.sample, lambda result: self._publish_state(entity, result))

    def _publish_state(self, entity, result: SampleResult) -> None:
        if not result.is_available:
            logging.debug("entity %s unavailable: %s", entity.key, result.reason)
            return
        topic = self._ctx.state_topic(entity.component, entity.key)
        self._session.publish(topic, _serialize(result.value), retain=True)

    def on_ha_status(self, payload: str) -> None:
        if payload.strip().lower() == "online":
            logging.info("Home Assistant came online — re-publishing discovery")
            self.apply()
            for entity in self._enabled_entities():
                self.tick(entity)

    def _restart_timers(self) -> None:
        for timer in self._timers.values():
            timer.stop()
        self._timers.clear()
        for entity in self._enabled_entities():
            if entity.is_event_driven:
                continue
            interval = self._settings.interval_s(entity.key, entity.default_interval_s or 30)
            timer = QTimer()
            timer.setInterval(int(interval) * 1000)
            timer.timeout.connect(lambda e=entity: self.tick(e))
            timer.start()
            self._timers[entity.key] = timer

    def stop(self) -> None:
        for timer in self._timers.values():
            timer.stop()
        self._timers.clear()
        for entity in self._entities:
            if entity.is_event_driven:
                try:
                    entity.unsubscribe()
                except (AttributeError, NotImplementedError):
                    pass

    def delete_all_for_current_device(self) -> None:
        for ref in self._previous_refs():
            topic = self._ctx.discovery_topic(ref.component, ref.key)
            self._session.publish(topic, "", retain=True)
