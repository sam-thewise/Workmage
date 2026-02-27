"""Capability plugin interfaces for action-oriented agents."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class CapabilityContext:
    """Common runtime context passed to capabilities."""

    agent_id: int | None
    network: str
    manifest: dict[str, Any]


class SignalWatcher(Protocol):
    """Produces normalized signals from external systems."""

    name: str

    async def watch(self, ctx: CapabilityContext) -> list[dict[str, Any]]:
        """Return a list of signal payloads."""


class Analyzer(Protocol):
    """Analyzes a signal and emits structured findings."""

    name: str

    async def analyze(self, signal: dict[str, Any], ctx: CapabilityContext) -> dict[str, Any]:
        """Return structured analysis."""


class Decider(Protocol):
    """Turns analysis into execution intent."""

    name: str

    async def decide(self, analysis: dict[str, Any], ctx: CapabilityContext) -> dict[str, Any]:
        """Return a decision object with action + parameters."""


class Executor(Protocol):
    """Executes a simulated or live action."""

    name: str

    async def execute(self, decision: dict[str, Any], ctx: CapabilityContext) -> dict[str, Any]:
        """Return execution receipt."""


class CapabilityRegistry:
    """In-memory registry for capability components."""

    def __init__(self) -> None:
        self.watchers: dict[str, SignalWatcher] = {}
        self.analyzers: dict[str, Analyzer] = {}
        self.deciders: dict[str, Decider] = {}
        self.executors: dict[str, Executor] = {}

    def register_watcher(self, watcher: SignalWatcher) -> None:
        self.watchers[watcher.name] = watcher

    def register_analyzer(self, analyzer: Analyzer) -> None:
        self.analyzers[analyzer.name] = analyzer

    def register_decider(self, decider: Decider) -> None:
        self.deciders[decider.name] = decider

    def register_executor(self, executor: Executor) -> None:
        self.executors[executor.name] = executor

    def get_component(self, kind: str, name: str) -> Any:
        source = {
            "watcher": self.watchers,
            "analyzer": self.analyzers,
            "decider": self.deciders,
            "executor": self.executors,
        }.get(kind)
        if source is None:
            raise ValueError(f"Unknown component kind: {kind}")
        if name not in source:
            raise KeyError(f"{kind} `{name}` is not registered")
        return source[name]


registry = CapabilityRegistry()
