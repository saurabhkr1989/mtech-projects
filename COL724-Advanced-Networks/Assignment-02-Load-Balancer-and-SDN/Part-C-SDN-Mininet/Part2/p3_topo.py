"""
Custom Mininet Topology (Part 2 & 3)

This script builds the specific 4-switch, 4-host ring topology required for the assignment.

"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.link import TCLink
from mininet.topo import Topo
from mininet.cli import CLI

class CustomRingTopology(Topo):
    """Our custom 4-switch, 4-host ring."""
    
    def build(self):
        """This method is called by Mininet to build the topology."""
        
        # --- 1. Add Switches ---
        # We create four switches and tell them to use OpenFlow 1.3. We also assign a simple, static DataPath ID (dpid) to each. This makes it easy to map "s1" to switch ID 1 in our controller.
        print("Adding switches...")
        s1 = self.addSwitch('s1', dpid='0000000000000001', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', dpid='0000000000000002', protocols='OpenFlow13')
        s3 = self.addSwitch('s3', dpid='0000000000000003', protocols='OpenFlow13')
        s4 = self.addSwitch('s4', dpid='0000000000000004', protocols='OpenFlow13')

        # --- 2. Add Hosts ---
        # We create four hosts, one for each switch. We give them static MAC and IP addresses for easy testing and to match the controller's log output.
        print("Adding hosts...")
        h1 = self.addHost('h1', ip='10.0.0.1/24', mac='00:00:00:00:00:01')
        h2 = self.addHost('h2', ip='10.0.0.2/24', mac='00:00:00:00:00:02')
        h3 = self.addHost('h3', ip='10.0.0.3/24', mac='00:00:00:00:00:03')
        h4 = self.addHost('h4', ip='10.0.0.4/24', mac='00:00:00:00:00:04')
        
        # --- 3. The Bufferbloat Fix ---
        MAX_QUEUE_PACKETS = 5

        # --- 4. Link Hosts to Switches ---
        # We use TCLink to control the bandwidth (bw=1 Mbps). We explicitly map each host to Port 1 on its switch. This MUST match the controller's logic (which assumes hosts are on port 1). Host ports (port1) are 0 by convention, but switch ports (port2) are critical.
        print("Linking hosts to switches (1 Mbps)...")
        self.addLink(h1, s1, port1=0, port2=1, bw=1, delay='1ms', cls=TCLink, max_queue_size=MAX_QUEUE_PACKETS)
        self.addLink(h2, s2, port1=0, port2=1, bw=1, delay='1ms', cls=TCLink, max_queue_size=MAX_QUEUE_PACKETS)
        self.addLink(h3, s3, port1=0, port2=1, bw=1, delay='1ms', cls=TCLink, max_queue_size=MAX_QUEUE_PACKETS)
        self.addLink(h4, s4, port1=0, port2=1, bw=1, delay='1ms', cls=TCLink, max_queue_size=MAX_QUEUE_PACKETS)

        # --- 5. Link Switches in a Ring ---
        # This is the core topology. We explicitly define the port numbers
        # (port1, port2) for every link.
        print("Linking switches in a ring...")
        
        # s1(port 2) <-> s2(port 2) --- FAST LINK (2 Mbps)
        self.addLink(s1, s2, port1=2, port2=2, bw=2, delay='20ms', cls=TCLink, max_queue_size=MAX_QUEUE_PACKETS)
        
        # s2(port 3) <-> s3(port 2) --- FAST LINK (2 Mbps)
        self.addLink(s2, s3, port1=3, port2=2, bw=2, delay='10ms', cls=TCLink, max_queue_size=MAX_QUEUE_PACKETS)
        
        # s3(port 3) <-> s4(port 2) --- SLOW LINK (1 Mbps)
        self.addLink(s3, s4, port1=3, port2=2, bw=1, delay='20ms', cls=TCLink, max_queue_size=MAX_QUEUE_PACKETS)
        
        # s4(port 3) <-> s1(port 3) --- SLOW LINK (1 Mbps)
        self.addLink(s4, s1, port1=3, port2=3, bw=1, delay='15ms', cls=TCLink, max_queue_size=MAX_QUEUE_PACKETS)

def run_network():
    """Main function to start and run the Mininet network."""
    
    # Set up the topology
    topo = CustomRingTopology()
    
    # Create the Mininet network object
    net = Mininet(
        topo=topo,
        switch=OVSKernelSwitch,  # Use OVS switches
        link=TCLink,             # Use TCLink for bandwidth control
        controller=None,         # We will add the controller manually
        build=False              # Don't build yet
    )
    
    # --- Add the Remote Controller ---
    # This tells Mininet to connect all switches to our Ryu controller.
    # Make sure your controller is running on this IP and port.
    # (10.0.2.15 is a common IP for the host if Mininet is in a VM,
    #  use 127.0.0.1 if Ryu is running on the same machine).
    controller_ip = '10.0.2.15' # <-- IMPORTANT: CHANGE THIS if ryu is local
    # controller_ip = '127.0.0.1' 
    
    net.addController(
        'remote_controller',
        controller=RemoteController,
        ip=controller_ip,
        port=6633
    )

    # Build and start the network
    print("Building network...")
    net.build()
    print("Starting network...")
    net.start()

    # Drop the user into the Mininet command-line interface
    print("\nNetwork is running.")
    CLI(net)

    # When the user types 'exit', stop the network
    print("Stopping network...")
    net.stop()

if __name__ == '__main__':
    # This block runs if the script is executed directly
    run_network()

