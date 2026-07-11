"""The tick loop: project -> decide -> execute -> append. Mode-agnostic."""
from __future__ import annotations

from typing import Protocol

from hunt.clock import Clock
from hunt.events import Event
from hunt.policy import Action, PolicyConfig, decide
from hunt.state import project
from hunt.store import EventStore


class Executor(Protocol):
    """Executes one action, returning the events it produced."""

    def execute(self, action: Action) -> list[Event]: ...


def run_tick(store: EventStore, config: PolicyConfig,
             executor: Executor, clock: Clock) -> tuple[Action, list[Event]]:
    """Run one tick; returns the decided action and the appended events."""
    state = project(store.read_all())
    action = decide(state, clock.now(), config)
    produced = executor.execute(action)
    appended = [store.append(e) for e in produced]
    return action, appended
