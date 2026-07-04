"""Shared-memory command bus: the attack surface.

The cohort coordinates through one shared blackboard file (`shared_memory.json`)
that holds the *latest* command. Any writer with access can overwrite it -- the
mission planner at t=0 (benign) or a compromised source at t=k (poison). Every
write is also appended to `memory_log.jsonl` so the whole episode is auditable:
you can replay exactly what the agent believed at every instant and who told it.

Memory record schema (one JSON object):
    {
      "timestamp":     <float seconds, wall or mission clock>,
      "source":        "mission_planner" | "A0" | ...,
      "trusted_claim": "<natural-language justification the agent 'trusts'>",
      "attack_type":   "none" | "memory_poisoning" | ...,
      "action":        "goto" | "inspect" | "rtl",
      "target_north":  <float>, "target_east": <float>, "target_down": <float>,
      "confidence":    <float 0..1>,
      "poisoned":      <bool>   # ground-truth label for scoring ONLY
    }
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Optional

import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

# Active memory paths. Default to the repo-level files (used by separate-process
# PX4 runs); an offline orchestrator can redirect them into a per-run folder via
# set_paths() so every scenario keeps its own shared_memory + audit log.
_SHARED_PATH = config.SHARED_MEMORY_FILE
_LOG_PATH = config.MEMORY_LOG_FILE


def set_paths(shared_memory_file: str, memory_log_file: str) -> None:
    global _SHARED_PATH, _LOG_PATH
    _SHARED_PATH = shared_memory_file
    _LOG_PATH = memory_log_file
    os.makedirs(os.path.dirname(shared_memory_file), exist_ok=True)
    os.makedirs(os.path.dirname(memory_log_file), exist_ok=True)


def shared_path() -> str:
    return _SHARED_PATH


def log_path() -> str:
    return _LOG_PATH


@dataclass
class MemoryRecord:
    source: str
    action: str
    target_north: float
    target_east: float
    target_down: float
    trusted_claim: str = ""
    attack_type: str = "none"
    confidence: float = 1.0
    poisoned: bool = False
    timestamp: float = field(default_factory=time.time)

    @property
    def target(self) -> tuple[float, float, float]:
        return (self.target_north, self.target_east, self.target_down)

    @classmethod
    def from_dict(cls, d: dict) -> "MemoryRecord":
        return cls(
            source=d.get("source", "unknown"),
            action=d.get("action", "goto"),
            target_north=float(d["target_north"]),
            target_east=float(d["target_east"]),
            target_down=float(d["target_down"]),
            trusted_claim=d.get("trusted_claim", ""),
            attack_type=d.get("attack_type", "none"),
            confidence=float(d.get("confidence", 1.0)),
            poisoned=bool(d.get("poisoned", False)),
            timestamp=float(d.get("timestamp", time.time())),
        )


def write_memory(record: MemoryRecord, *, log: bool = True) -> None:
    """Atomically publish `record` as the active shared command and append to log.

    The write is atomic (write-temp-then-rename) so a reader polling the file
    never sees a half-written command -- this matters because the victim agent
    re-reads memory every control tick, concurrently with the launcher's write.
    """
    payload = asdict(record)
    tmp = _SHARED_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, _SHARED_PATH)
    if log:
        append_log(payload)


def append_log(payload: dict) -> None:
    with open(_LOG_PATH, "a") as f:
        f.write(json.dumps(payload) + "\n")


def read_memory() -> Optional[MemoryRecord]:
    """Return the current shared command, or None if memory is empty/absent."""
    try:
        with open(_SHARED_PATH, "r") as f:
            return MemoryRecord.from_dict(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def reset_log() -> None:
    """Truncate the audit log (call once at the start of a fresh episode)."""
    open(_LOG_PATH, "w").close()


def seed_safe_command(clock: float = 0.0) -> MemoryRecord:
    """Publish the benign mission-planner command that starts every episode."""
    rec = MemoryRecord(
        source=config.TRUSTED_SOURCE,
        action="goto",
        target_north=config.SAFE_WAYPOINT["north"],
        target_east=config.SAFE_WAYPOINT["east"],
        target_down=config.SAFE_WAYPOINT["down"],
        trusted_claim="Proceed to survey waypoint ahead of the restricted area.",
        attack_type="none",
        confidence=1.0,
        poisoned=False,
        timestamp=clock,
    )
    write_memory(rec)
    return rec
