#SDN Controller Comparison: Hub vs. Learning Switch

**This project demonstrates the fundamental difference between two basic types of SDN controllers using Ryu and Mininet:

	*Hub Controller (p1-hub.py): A "dumb" controller that instructs switches to behave like a simple hub. It tells the switch to flood every incoming packet to all other ports. This is highly inefficient.

	*Learning Switch Controller (p1-learning.py): A "smart" controller that implements L2 learning. It learns the location (MAC address) of hosts as it sees traffic and installs specific flow rules on the switches. This allows subsequent packets to be handled directly by the switch hardware, which is extremely fast and efficient.

	*The p1_topo.py script creates the virtual network topology in Mininet (2 switches, 5 hosts) that we use to test and compare these two controllers.

#File Descriptions

	*p1-hub.py: The Ryu controller application that makes switches act as hubs.

	*p1-learning.py: The Ryu controller application that makes switches act as L2 learning switches.

	*p1_topo.py: The Mininet topology script to create the virtual network.

#Instructions to Run the Program

	*You will need two separate terminals running at the same time.

	*Terminal 1: Will run the Ryu Controller.

	*Terminal 2: Will run the Mininet Network.

	**Step 1: Start the Ryu Controller (Terminal 1)

		*First, choose which controller you want to test. You can only run one at a time.

		*Navigate to the directory containing the files. The | tee command will show the output on your console and save it to the specified log file.

		`To test the HUB Controller. Run the following command:

			**ryu-manager p1-hub.py 2>&1| tee hub_controller.log


		`To test the LEARNING SWITCH Controller. Run the following command:

			**ryu-manager p1-learning.py 2>&1 | tee learning_switch_controller.log

			*This terminal will now wait for switches to connect, showing you the live log.

	**Step 2: Edit and Start the Mininet Network (Terminal 2)

		*Before you run the topology, you must edit the controller's IP address in the p1_topo.py file.

		*Open p1_topo.py with a text editor.

		*Find this line:

		*net.addController('c0', controller=RemoteController, ip="10.0.2.15", port=6633)

		*Change the ip="10.0.2.15" to the IP address of the machine running Ryu.

		*Save the file.

		*Now, run the topology script using sudo:
		
		*To enable logging of mininet run "script mininet_hub_controller.log" or "script mininet_learning_switch.log"

		**sudo python3 p1_topo.py

		*You will see Mininet start up and the switches connect to the controller in Terminal 1. You will now have a mininet> prompt in Terminal 2.

#Testing and Comparing Controllers

	*You can now run tests from the mininet> prompt (Terminal 2) to see the difference.

	**1. Test Connectivity (pingall)

		*This command makes all hosts ping each other.

		**mininet> pingall


		*With Hub: You will see a massive storm of log messages in the Ryu terminal (Terminal 1) because every single ping packet is being sent to the controller.

		*With Learning Switch: You will see a small burst of logs for the first few packets. After that, the Ryu terminal will become quiet because the controller has installed flow rules, and the switches are handling the pings themselves.

	**2. Test Throughput (iperf)

		*This command tests the maximum speed between two hosts.

		**mininet> iperf h1 h5


		*With Hub: The speed will be very low (e.g., < 10 Mbps). This is because the controller is the bottleneck.

		*With Learning Switch: The speed will be very high (e.g., > 1 Gbps). This is because the switch hardware is handling the traffic at line-rate.

	**3. Inspect Switch Flow Rules

		*This command shows you the "rules" installed on the switch.

		**mininet> sh ovs-ofctl dump-flows s1


		*With Hub: You will only see one rule: the default "table-miss" rule that sends everything to the CONTROLLER.

		*With Learning Switch: You will see the default rule plus several higher-priority rules that match specific MAC addresses (e.g., eth_src=... eth_dst=...) and send them to the correct output por