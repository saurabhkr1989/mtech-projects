#Proactive Shortest Path Routing with Ryu & Mininet 

**This project demonstrates a smart, proactive network controller built with Ryu that manages a custom Mininet topology.

**Instead of just flooding packets like a simple switch, this controller intelligently calculates the fastest path (based on link bandwidth, not just hop count) for traffic and installs routing rules on the switches. It's designed to be efficient, avoiding broadcast storms and ensuring the network is ready for traffic from the moment it starts.

#Key Features

	*Custom Ring Topology: The p3_topo.py script builds a specific 4-switch, 4-host ring network with varying link speeds (1 Mbps and 2 Mbps).

	*Bandwidth-Aware Routing: The controller knows the network map in advance. When a new connection starts (e.g., a ping), it uses Dijkstra's algorithm to find the path with the highest total bandwidth.

	*Proactive ARP Handling: As soon as all switches connect, the controller automatically probes the network to learn the location of every host. This populates its ARP table instantly, preventing the broadcast storms that typically happen when hosts first try to find each other. The result? A perfectly clean pingall with 100% success on the first try!

	*Dynamic Flow Installation: Rules are pushed to the switches on-demand. Once a path is calculated, flow rules are installed along that path so subsequent packets are handled at line-speed by the switches themselves, without needing to ask the controller again.

	*Color-Coded Logging: The controller's terminal output is color-coded to make it easy to see what's happening—when switches connect, when hosts are learned, and when paths are being calculated.

#How to Run the Simulation

	*You'll need two separate terminal windows on your Mininet VM for this. One will run the Ryu controller, and the other will run the Mininet network simulation.

	`Terminal 1 : Start the Ryu Controller

	*Navigate to the directory where you've saved the files.

	*Start the Ryu controller by running:

		**ryu-manager shortestpath_controller.py > shortestpath_controller.txt 2>&1


		*The controller will start and print a "Started Shortest Path Controller" message. It will now wait patiently for the switches from Mininet to connect.

	`Terminal 2️ : Start the Mininet Topology

	**IMPORTANT IP CHECK: Before you start, open the p3_topo.py file and look for the controller_ip variable.

	*If you are running Ryu and Mininet on the same machine (e.g., directly on your Linux desktop), change the IP to '127.0.0.1'.

	*If you are using the standard Mininet VM (running in VirtualBox or VMware), the default IP of '10.0.2.15' is likely correct, as this is how the VM typically communicates with the host machine.

	*In your second terminal, navigate to the same directory.

	*Run the Mininet script using sudo:

		**sudo python p3_topo.py


	*You'll see output as Mininet builds the topology, adds hosts and switches, and links them together.

#What to Expect

	*In the Ryu Terminal: As Mininet starts, you will see logs appear as each of the four switches connects. Once all four are connected, you'll see the proactive ARP probing begin.

	*In the Mininet Terminal: Once the network is running, you will be dropped into the Mininet command-line interface (mininet>).

	`Testing the Network

	*Now you can test the network!

	*Run pingall:

		**mininet> pingall


	*You should see 0% packet loss. Check the Ryu terminal—you'll notice no ARP broadcasts were flooded. The controller handled them all!

	*Test the Shortest Path: Let's send traffic between h1 and h3. The network has two paths:

			**s1 -> s2 -> s3 (fast path, 2 Mbps)

			**s1 -> s4 -> s3 (slow path, 1 Mbps)

	*The controller should choose the faster path.

	`In the Mininet CLI, start an iperf server on h1:

		**mininet> h1 iperf -s


	`In the Mininet CLI, start an iperf client on h3 to connect to h1:

		**mininet> h3 iperf -c 10.0.0.1


	*Now, look at your Ryu controller terminal. You will see a log message showing the calculated shortest path, which should be [1, 2, 3], confirming it chose the high-bandwidth route. The iperf test should report a bandwidth of around 2 Mbits/sec.

	`To exit, type exit in the Mininet CLI and press Ctrl+C in the Ryu terminal. Don't forget to run sudo mn -c in the Mininet terminal to clean up any leftover network interfaces.