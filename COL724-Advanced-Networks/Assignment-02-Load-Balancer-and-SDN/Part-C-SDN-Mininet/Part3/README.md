#Congestion-Aware Dynamic Routing with Ryu & Mininet

	*This project demonstrates a smart Software-Defined Networking (SDN) controller that dynamically routes traffic based on real-time network congestion.

	*It uses Ryu as the SDN controller and Mininet to emulate the network topology.

#Overview

*In a traditional network, traffic between two points often takes a single, static "shortest" path, even if that path becomes congested. This controller solves that problem. It actively monitors the traffic on all network links. When a link becomes busy, the controller increases its "cost" (weight). New traffic flows are then intelligently routed along the least congested path, which may not be the shortest physical path.

#Components

	`congestion_controller.py:

		*This is the "brain" of the operation. It's a Ryu controller application.

		*It learns where hosts are on the network (L2 learning).

		*It runs a background thread to poll all switches every 5 seconds for port statistics (bytes sent).

		*It calculates the real-time utilization (%) of each inter-switch link.

		*It dynamically updates a network graph with new "weights" for each link. The weight is a combination of the link's base cost (1/bandwidth) and a penalty based on its current congestion.

		*It installs flow rules with a hard_timeout, forcing flows to be re-evaluated periodically, allowing the controller to reroute active traffic if a better path becomes available.

	`p3_topo.py:

		*This is a Mininet script that builds the virtual network.

		*It creates a topology of 4 switches (s1-s4) and 4 hosts (h1-h4), one host per switch.

		*The switches are connected in a ring with asymmetric bandwidths:

			`s1 <-> s2: 2 Mbps

			`s2 <-> s3: 2 Mbps

			`s3 <-> s4: 1 Mbps

			`s4 <-> s1: 1 Mbps

		*This asymmetric design is perfect for testing the controller, as the "shortest" path might also be the "slowest" if it's congested.

#Requirements

	**Ryu: An open-source SDN controller framework.

	**Mininet: A network emulator for creating virtual network topologies.

#How to Run the Simulation

	You will need two separate terminal windows for this.

		**Terminal 1: Start the Ryu Controller

			*Navigate to the directory containing congestion_controller.py.

			*Run the controller using ryu-manager:

			**ryu-manager congestion_controller.py


			*You should see logs indicating the controller has started and is waiting for switches to connect. This terminal will show the live statistics and dynamic weight changes as traffic flows. Keep an eye on it!

				`Static network topology and port speeds loaded.
				`Started congestion monitoring thread (Polls every 5 sec)
				`Switch 1 connected.
				`Switch 2 connected.


		**Terminal 2: Start the Mininet Topology

			*Important: Before you start, you must edit p3_topo.py. Find this line:

			*ctrl = net.addController('c0', controller=RemoteController, ip='10.0.2.15', port=6633)


			*Change the ip='10.0.2.15' to the IP address of the machine where you are running the Ryu controller (Terminal 1). If you are running both on the same VM, this is often 127.0.0.1.

			*Once the IP is corrected, run the Mininet script as root:

			**sudo python3 p3_topo.py


			*If successful, Mininet will start, connect to the Ryu controller, and you will see a mininet> prompt.

#Step 3: Test the Dynamic Routing

	*In the mininet> prompt (Terminal 2), start a long-running iperf test between h1 and h3. This will send a large amount of traffic.

		**mininet> iperf h1 h3


	*or for a longer test:

		**mininet> iperf h1 h3 -t 30


	`Watch Terminal 1 (Ryu). You will see the controller's logs come alive! Every 5 seconds, you will see output like this:

			Switch 1 Port 2: 85.12% utilization
			Switch 2 Port 2: 84.99% utilization
			
			Updating link weights in graph...
			  -> Link 1->2 (Port 2): Util=85.12%, New_Weight=9.01
			  -> Link 2->1 (Port 2): Util=84.99%, New_Weight=8.99
			  -> Link 2->3 (Port 3): Util=0.00%, New_Weight=0.50
			
			Calculating path for ... (Switch 1 to 3)...
			Path found: [1, 4, 3]


	**This output is proof that the controller is:
	a.  Seeing the congestion on the s1 <-> s2 path.
	b.  Dramatically increasing the "weight" of that path (e.g., to 9.01).
	c.  When the flow rule expires, it recalculates the path and finds a new, less congested route (e.g., [1, 4, 3]).

	*You can try starting a second iperf in another xterm (xterm h2 h4) to see how the controller balances multiple flows.