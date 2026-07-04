"""Flight backends for the victim agent.

The victim's control loop is backend-agnostic:  read memory -> command a target
-> observe position -> log.  Only *how* a target is commanded and *how* position
is observed differs between backends, so both implement the same async interface:

    await backend.start()                 # connect / arm / takeoff / offboard
    await backend.goto(n, e, d)           # command an absolute NED target
    (n, e, d) = await backend.position()  # current NED position
    await backend.land()

`px4`  -> real MAVSDK offboard against PX4 SITL + Gazebo (identical to the
          original baseline_memory_attack.py proof).
`sim`  -> a first-order kinematic integrator (no PX4 needed) so the entire
          attack pipeline is reproducible offline and in CI. It mirrors the
          professor's sim/drone.py step model (velocity integration toward the
          commanded target, capped at cruise speed).
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402


class SimBackend:
    """Offline first-order kinematic drone. Deterministic, no external deps."""

    def __init__(self, dt: float = config.CONTROL_DT, speed: float = config.CRUISE_SPEED):
        self.dt = dt
        self.speed = speed
        self._n, self._e, self._d = config.START_NED
        self._target = (self._n, self._e, self._d)

    async def start(self) -> None:
        # Drone begins hovering at the nominal post-takeoff position.
        self._n, self._e, self._d = config.START_NED

    async def goto(self, north: float, east: float, down: float) -> None:
        """Set the target and integrate one tick toward it, capped at cruise speed."""
        self._target = (north, east, down)
        max_step = self.speed * self.dt
        for i, cur in enumerate((self._n, self._e, self._d)):
            delta = self._target[i] - cur
            if abs(delta) > max_step:
                delta = max_step if delta > 0 else -max_step
            new = cur + delta
            if i == 0:
                self._n = new
            elif i == 1:
                self._e = new
            else:
                self._d = new

    async def position(self) -> tuple[float, float, float]:
        return (self._n, self._e, self._d)

    async def land(self) -> None:
        return None


class Px4Backend:
    """Real MAVSDK offboard backend against PX4 SITL + Gazebo."""

    def __init__(self, address: str = config.PX4_ADDRESS,
                 altitude: float = config.CRUISE_ALTITUDE_M):
        self.address = address
        self.altitude = altitude
        self._drone = None

    async def start(self) -> None:
        from mavsdk import System
        from mavsdk.offboard import OffboardError, PositionNedYaw

        self._drone = System()
        await self._drone.connect(system_address=self.address)

        print(f"[px4] waiting for connection on {self.address} ...")
        async for state in self._drone.core.connection_state():
            if state.is_connected:
                print("[px4] connected")
                break

        print("[px4] arming")
        await self._drone.action.arm()

        print(f"[px4] taking off to {self.altitude} m")
        await self._drone.action.set_takeoff_altitude(self.altitude)
        await self._drone.action.takeoff()

        # Wait until the vehicle is actually airborne before switching to offboard.
        await asyncio.sleep(6)
        async for in_air in self._drone.telemetry.in_air():
            if in_air:
                break
        await asyncio.sleep(2)

        n, e, d = await self.position()
        hold = PositionNedYaw(n, e, -self.altitude, 0.0)

        # PX4 rejects offboard unless a setpoint stream is already flowing; prime
        # it for ~1 s, then start, retrying a few times on COMMAND_DENIED.
        for attempt in range(5):
            for _ in range(20):
                await self._drone.offboard.set_position_ned(hold)
                await asyncio.sleep(0.05)
            try:
                await self._drone.offboard.start()
                print(f"[px4] offboard started (attempt {attempt + 1})")
                return
            except OffboardError as err:
                print(f"[px4] offboard start denied (attempt {attempt + 1}): {err}")
                await asyncio.sleep(0.5)
        raise RuntimeError("offboard start failed after retries")

    async def goto(self, north: float, east: float, down: float) -> None:
        from mavsdk.offboard import PositionNedYaw
        await self._drone.offboard.set_position_ned(
            PositionNedYaw(north, east, down, 0.0)
        )

    async def position(self) -> tuple[float, float, float]:
        async for pv in self._drone.telemetry.position_velocity_ned():
            p = pv.position
            return (p.north_m, p.east_m, p.down_m)
        return config.START_NED

    async def land(self) -> None:
        try:
            await self._drone.offboard.stop()
        except Exception:
            pass
        await self._drone.action.land()


def make_backend(name: str):
    name = name.lower()
    if name == "sim":
        return SimBackend()
    if name == "px4":
        return Px4Backend()
    raise ValueError(f"unknown backend: {name!r} (use 'sim' or 'px4')")
