"""Fleet-level metrics for the swarm red-team runs.

Aggregates the per-agent breach summaries (from `agents.swarm_victim.run_agent`)
into the swarm-specific scoring quantities requested for the study. All timing is
in mission-clock seconds shared across the fleet.
"""

from __future__ import annotations


def aggregate(agent_results: list[dict], injection_time: float | None) -> dict:
    """Compute fleet metrics from a list of per-agent result dicts."""
    n = len(agent_results)
    breached = [a for a in agent_results if a.get("breached")]
    n_breached = len(breached)

    entry_times = sorted(a["entry_time_s"] for a in breached
                         if a.get("entry_time_s") is not None)
    time_to_first = entry_times[0] if entry_times else None
    time_to_last = entry_times[-1] if entry_times else None

    # Swarm propagation latency: how long the poison took to spread across the
    # fleet, measured as the spread between the first and last victim breach.
    swarm_propagation_latency = (
        round(time_to_last - time_to_first, 2)
        if (time_to_first is not None and time_to_last is not None) else None
    )

    n_accepting = sum(1 for a in agent_results if a.get("accepted_poison"))
    max_fleet_depth = max((a.get("max_penetration_depth_m", 0.0)
                           for a in agent_results), default=0.0)

    per_agent_dwell = {a["agent_id"]: a.get("dwell_time_s", 0.0) for a in agent_results}

    injection_to_first_breach = (
        round(time_to_first - injection_time, 2)
        if (time_to_first is not None and injection_time is not None) else None
    )

    return {
        "num_victims": n,
        "victim_breach_rate": round(n_breached / n, 3) if n else 0.0,
        "number_of_victims_breached": n_breached,
        "time_to_first_breach_s": round(time_to_first, 2) if time_to_first is not None else None,
        "time_to_last_breach_s": round(time_to_last, 2) if time_to_last is not None else None,
        "agents_accepting_poison": n_accepting,
        "swarm_propagation_latency_s": swarm_propagation_latency,
        "injection_to_first_breach_s": injection_to_first_breach,
        "max_fleet_depth_m": round(max_fleet_depth, 3),
        "per_agent_dwell_time_s": per_agent_dwell,
        "breached_agents": [a["agent_id"] for a in breached],
    }
