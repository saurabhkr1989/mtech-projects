# Advanced Computer Networks (COL724 / COL7524)

M.Tech (Cyber Security), Semester I, IIT Delhi. COL7524 is the lab component paired with the
COL724 lecture course.

| Item | Description |
|------|-------------|
| [Assignment 1](./Assignment-01-NS3-BGP-Simulation) | ns-3 simulations of BGP routing behavior, Parts A-E, each with its own write-up |
| [Assignment 2](./Assignment-02-Load-Balancer-and-SDN) | Part A/B: C++ socket-programming load balancers (echo + file transfer); Part C: SDN/Mininet controllers (hub, learning switch, shortest-path, congestion-aware) |
| [Project Proposal](./Project-Proposal-TIMELY-Congestion-Control) | Review and simulation of the TIMELY RDMA congestion-control paper, compared against DCTCP |

Where an assignment had multiple submission attempts on disk, the most complete/final attempt
was kept and the rest discarded. Software installers (Cisco Packet Tracer) and a Cisco IOS
firmware image found in the original folder were excluded — not safe to redistribute publicly.
Compiled binaries, build artifacts, and placeholder test-data files are excluded (see repo root
`.gitignore`); the C++ load-balancer code still includes its `Makefile` so it can be rebuilt.
