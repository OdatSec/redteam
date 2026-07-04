"""In-process shared-memory blackboard for the swarm extension.

The single-victim harness (`agents/memory_bus.py`) coordinates through a global
on-disk file with one *latest* command; that fits one reader/one writer in
separate processes. The swarm runs A0 (attacker) + A1/A2/A3 (victims) + a
benign Mission Coordinator concurrently inside ONE asyncio process, so here the
shared memory is a small in-process object instead.

It keeps the SAME threat model as the single-victim study: one shared blackboard
that any writer can post to, and that every victim independently reads. Messages
carry a `target_agent` ("all" for a broadcast, or a specific victim id) so the
coordinator can hand each drone its benign assignment while the attacker's
poison is broadcast to the whole fleet. Every write is appended to a JSONL audit
log so an episode can be replayed exactly: who wrote what, when, and to whom.

This module performs NO safety filtering or NFZ reasoning — it is a dumb bus, so
the victims remain vulnerable baselines (swarm scope: no defense).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from agents.memory_bus import MemoryRecord

BROADCAST = "all"


class SwarmMemoryBus:
    """A single shared blackboard read by the whole fleet.

    Records are stored in write order. `latest_for(agent_id)` returns the most
    recent record addressed to that agent (or broadcast) — this is what makes a
    later broadcast poison supersede an earlier per-agent benign assignment.
    """

    def __init__(self, log_path: str):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        open(log_path, "w").close()          # fresh audit log per episode
        self._counter = 0
        self._records: list[tuple[str, MemoryRecord]] = []

    def write(self, record: MemoryRecord, *, target_agent: str = BROADCAST,
              clock: float | None = None) -> MemoryRecord:
        """Post a record to the blackboard and append it to the audit log."""
        record.memory_id = f"m{self._counter}"
        self._counter += 1
        if clock is not None:
            record.timestamp = clock
        self._records.append((target_agent, record))
        payload = asdict(record)
        payload["target_agent"] = target_agent
        with open(self.log_path, "a") as f:
            f.write(json.dumps(payload) + "\n")
        return record

    def latest_for(self, agent_id: str) -> MemoryRecord | None:
        """Most recent record visible to `agent_id` (its own or a broadcast)."""
        for target, rec in reversed(self._records):
            if target == BROADCAST or target == agent_id:
                return rec
        return None

    def all_records(self) -> list[tuple[str, MemoryRecord]]:
        return list(self._records)
