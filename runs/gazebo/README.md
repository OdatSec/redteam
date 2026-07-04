# PX4 + Gazebo results

Real flight via **MAVSDK offboard** against PX4 SITL + Gazebo (`gz_x500`).

May include Gazebo-specific videos:
- `08_gazebo_flight_recording_3d.mp4`
- `09_gazebo_and_map_split_screen.mp4`

```bash
PX4_GZ_WORLD=nfz_restricted_zone make px4_sitl gz_x500   # Terminal 1
python run_experiment.py --scenario runtime_behind --backend px4   # Terminal 2
```

Offline benchmark: [`../sim/`](../sim/)
