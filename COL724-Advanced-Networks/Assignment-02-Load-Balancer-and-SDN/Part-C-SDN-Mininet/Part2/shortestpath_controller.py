"""
Shortest Path Controller

This Ryu controller implements a sophisticated shortest path routing
solution for a known, static network topology.

It includes:
- A pre-loaded network graph with link weights based on bandwidth.
- A proactive ARP handler that learns all host IPs/MACs on startup to prevent broadcast storms and ensure 100% first-ping success.
- A dynamic IP path installer that calculates the shortest path for new flows and installs OpenFlow rules along that path.
- Colorized logging for easier debugging.
"""

# Standard Ryu libraries
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3

# Libraries for packet parsing
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ether_types
from ryu.lib.packet import arp
from ryu.lib.packet import ipv4
from ryu.lib.packet import icmp
from ryu.lib import mac as mac_lib

# Library for tracking switch connections
from ryu.topology import event

# Library for graph logic and shortest path calculation
import networkx as nx

# --- ANSI Color Codes for Logging ---
class Colors:
    """Class to hold ANSI color codes for terminal output."""
    RESET = '\033[0m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m' # For ARP

class ShortestPathRouter(app_manager.RyuApp):
    """The main controller class."""
    
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(ShortestPathRouter, self).__init__(*args, **kwargs)
        
        # { 'mac_address': (switch_id, port_number) }
        self.host_location_table = {}

        # { 'ip_address': 'mac_address' }
        self.arp_table = {}

        # { switch_id: datapath_object }
        self.active_switches = {}

        # The pre-loaded network map
        self.network_graph = nx.DiGraph()
        
        self.logger.info(f"{Colors.GREEN}Started Proactive Shortest Path Controller{Colors.RESET}")

    def _build_static_topology(self):
        """
        Builds the static, in-memory graph of the network topology.
        
        This is necessary because link properties like bandwidth are
        not advertised via the OpenFlow protocol. We must pre-load this
        information.
        
        Weights are set as the inverse of bandwidth (1/bw) so that
        Dijkstra's algorithm prefers higher-bandwidth links.
        """
        self.logger.info("Building static network map...")
        for switch_id in range(1, 5):
            self.network_graph.add_node(switch_id)
        
        # Link s1 <-> s2 (bw=2)
        self.network_graph.add_edge(1, 2, port=2, weight=1.0/2.0)
        self.network_graph.add_edge(2, 1, port=2, weight=1.0/2.0)
        # Link s2 <-> s3 (bw=2)
        self.network_graph.add_edge(2, 3, port=3, weight=1.0/2.0)
        self.network_graph.add_edge(3, 2, port=2, weight=1.0/2.0)
        # Link s3 <-> s4 (bw=1)
        self.network_graph.add_edge(3, 4, port=3, weight=1.0/1.0)
        self.network_graph.add_edge(4, 3, port=2, weight=1.0/1.0)
        # Link s4 <-> s1 (bw=1)
        self.network_graph.add_edge(4, 1, port=3, weight=1.0/1.0)
        self.network_graph.add_edge(1, 4, port=3, weight=1.0/1.0)
        
        self.logger.info(f"{Colors.GREEN}Static network topology loaded.{Colors.RESET}")

    # --- Switch Connection Handlers ---
    
    @set_ev_cls(event.EventSwitchEnter, [MAIN_DISPATCHER, CONFIG_DISPATCHER])
    def _switch_enter_handler(self, event):
        """Called when a new switch connects to the controller."""
        datapath = event.switch.dp
        switch_id = datapath.id
        self.active_switches[switch_id] = datapath
        self.logger.info(f"{Colors.GREEN}Switch {switch_id} has connected.{Colors.RESET}")
        
        # When all 4 switches are connected, proactively probe hosts
        # to fill the ARP table *before* pingall is even run.
        if len(self.active_switches) == 4:
            self._pre_learn_all_hosts()

    @set_ev_cls(event.EventSwitchLeave, [MAIN_DISPATCHER, CONFIG_DISPATCHER])
    def _switch_leave_handler(self, event):
        """Called when a switch disconnects."""
        datapath = event.switch.dp
        switch_id = datapath.id
        if switch_id in self.active_switches:
            del self.active_switches[switch_id]
            self.logger.info(f"{Colors.RED}Switch {switch_id} has disconnected.{Colors.RESET}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, event):
        """Called for the initial handshake with a switch."""
        datapath = event.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Also store the datapath object here
        self.active_switches[datapath.id] = datapath
        
        # Build the topology map once on the first switch connection
        if not self.network_graph.nodes():
            self._build_static_topology()

        # Install the "Table-Miss" Flow Rule (Priority 0)
        # This rule sends any packet that doesn't match an existing
        # flow rule to the controller.
        match_all = parser.OFPMatch()
        action_send_to_controller = [
            parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                  ofproto.OFPCML_NO_BUFFER)
        ]
        self.add_flow(datapath, 0, match_all, action_send_to_controller)

    # --- Proactive ARP Functions ---
    
    def _pre_learn_all_hosts(self):
        """
        Proactively probes all known host IPs to populate the ARP table before pingall is run.
        
        This logic commands each switch to probe its own host, which is much faster and more reliable than waiting for hosts to ARP each other.
        """
        self.logger.info(f"{Colors.CYAN}All switches connected. Proactively probing all hosts...{Colors.RESET}")
        
        # We need a "fake" sender for these packets.
        # We'll use h1's info, which we know from the topology.
        arp_sender_ip = '10.0.0.1'
        arp_sender_mac = '00:00:00:00:00:01'
        
        # Manually learn h1 (our sender) since it won't be probed
        self.host_location_table[arp_sender_mac] = (1, 1) # (switch_id=1, port=1)
        self.arp_table[arp_sender_ip] = arp_sender_mac

        # Iterate through all connected switches
        for switch_id, datapath in self.active_switches.items():
            
            # Don't make h1 (switch 1) probe for itself
            if switch_id == 1:
                continue

            # The IP we want to find, which corresponds to the switch ID
            target_ip = f'10.0.0.{switch_id}'

            self.logger.info(f"{Colors.CYAN}--> Commanding S{switch_id} to probe for {target_ip} on Port 1...{Colors.RESET}")
            
            # Forge an ARP request: "Who has {target_ip}? Tell {arp_sender_ip}"
            # Send this request *from* the target's own switch *to* its host port.
            self._send_arp_request(
                datapath=datapath,           # The datapath (e.g., s2)
                src_mac=arp_sender_mac,      # "From" h1's MAC
                src_ip=arp_sender_ip,        # "From" h1's IP
                target_ip=target_ip,         # "To" h2's IP
                output_port=1                # Send *only* to the host port (Port 1)
            )

    def _send_arp_request(self, datapath, src_mac, src_ip, target_ip, output_port):
        """
        Forges and sends an ARP request packet out of a specific switch and specific output port.
        """
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        
        # Forge Ethernet packet (Broadcast)
        e = ethernet.ethernet(
            dst=mac_lib.BROADCAST_STR,
            src=src_mac,
            ethertype=ether_types.ETH_TYPE_ARP
        )
        
        # Forge ARP packet
        a = arp.arp(
            hwtype=1, proto=0x0800, hlen=6, plen=4,
            opcode=arp.ARP_REQUEST,
            src_mac=src_mac,
            src_ip=src_ip,
            dst_mac=mac_lib.BROADCAST_STR,
            dst_ip=target_ip
        )
        
        p = packet.Packet()
        p.add_protocol(e)
        p.add_protocol(a)
        p.serialize()

        # Send the probe out of the specified host port
        actions = [ parser.OFPActionOutput(output_port) ]
        
        self._send_packet_out(datapath, None, actions, 
                              in_port=ofproto.OFPP_CONTROLLER, data=p.data)


    # --- Main Packet-In Handler ---
    
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, event):
        """
        Called every time a switch sends a packet to the controller.
        This is the main entry point for all network traffic.
        """
        message = event.msg
        datapath = message.datapath
        in_port = message.match['in_port']

        pkt = packet.Packet(message.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP packets (Link Layer Discovery Protocol)
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
            
        source_mac = eth.src
        switch_id = datapath.id

        # --- 1. Learn Source Host Location (MAC -> Switch/Port) ---
        # This is the "learning" part of a learning switch.
        if source_mac not in self.host_location_table:
            self.host_location_table[source_mac] = (switch_id, in_port)
            self.logger.info(f"{Colors.GREEN}Learned MAC: {source_mac} is at Switch {switch_id}, Port {in_port}{Colors.RESET}")

        # --- 2. Branch based on packet type ---
        if eth.ethertype == ether_types.ETH_TYPE_ARP:
            # Handle ARP to prevent broadcast storms
            self._handle_arp(datapath, in_port, pkt, eth)
        
        elif eth.ethertype == ether_types.ETH_TYPE_IP:
            # Handle IP by installing shortest path
            self._handle_ip(datapath, message, eth, in_port)
            
        else:
            self.logger.info(f"Ignoring unknown ethertype: {eth.ethertype}")


    # --- ARP Packet Handler ---
    
    def _handle_arp(self, datapath, in_port, pkt, eth_header):
        """
        Handles ARP packets to prevent broadcast storms. This function acts as a centralized ARP proxy.
        """
        arp_pkt = pkt.get_protocol(arp.arp)
        
        # --- 1. Learn Sender's IP-to-MAC mapping ---
        # This is how we build our ARP table (e.g., from replies)
        if arp_pkt.src_ip not in self.arp_table:
            self.arp_table[arp_pkt.src_ip] = arp_pkt.src_mac
            self.logger.info(f"{Colors.GREEN}Learned IP: {arp_pkt.src_ip} -> {arp_pkt.src_mac}{Colors.RESET}")

        # --- 2. Check if this is an ARP Request ---
        if arp_pkt.opcode != arp.ARP_REQUEST:
            # It's an ARP reply (e.g., from our proactive probe).
            # We've already learned the IP/MAC, so we're done.
            return

        self.logger.info(f"{Colors.MAGENTA}Handling ARP Request: Who has {arp_pkt.dst_ip}? Tell {arp_pkt.src_ip}{Colors.RESET}")

        # --- 3. Check if we know the MAC for the requested IP ---
        target_mac = self.arp_table.get(arp_pkt.dst_ip)

        if target_mac:
            # --- YES. We know this host. ---
            # We will forge an ARP reply and send it back to the sender.
            self.logger.info(f"{Colors.MAGENTA}--> Known! Replying: {arp_pkt.dst_ip} is at {target_mac}{Colors.RESET}")
            self._send_arp_reply(datapath, in_port, eth_header, arp_pkt, target_mac)
        
        else:
            # --- NO. We don't know this host. ---
            # This shouldn't happen if our proactive probes worked,
            # but we'll log it just in case.
            self.logger.warning(f"{Colors.RED}--> ERROR: Unknown IP {arp_pkt.dst_ip}. Proactive probe may have failed.{Colors.RESET}")
            # We drop the packet to prevent any chance of a storm.


    def _send_arp_reply(self, datapath, in_port, eth_header, arp_pkt, target_mac):
        """
        Forges and sends an ARP reply packet directly back to the original sender.
        """
        parser = datapath.ofproto_parser
        
        # Create the Ethernet header
        e = ethernet.ethernet(
            dst=eth_header.src,    # Send to original sender's MAC
            src=target_mac,        # "From" the MAC they were looking for
            ethertype=ether_types.ETH_TYPE_ARP
        )
        
        # Create the ARP header
        a = arp.arp(
            hwtype=arp_pkt.hwtype, proto=arp_pkt.proto,
            hlen=arp_pkt.hlen, plen=arp_pkt.plen,
            opcode=arp.ARP_REPLY,
            src_mac=target_mac,        # My MAC is...
            src_ip=arp_pkt.dst_ip,     # My IP is...
            dst_mac=arp_pkt.src_mac,   # For the original sender's MAC
            dst_ip=arp_pkt.src_ip      # For the original sender's IP
        )
        
        # Build the packet
        p = packet.Packet()
        p.add_protocol(e)
        p.add_protocol(a)
        p.serialize()

        # Send the packet out the same port it came in on
        actions = [parser.OFPActionOutput(in_port)]
        self._send_packet_out(datapath, None, actions, in_port=ofproto_v1_3.OFPP_CONTROLLER, data=p.data)
            
    # --- IP Packet Handler ---

    def _handle_ip(self, datapath, message, eth_header, in_port):
        """
        Handles IPv4 packets by calculating and installing
        the shortest-path flow rules.
        """
        parser = datapath.ofproto_parser
        switch_id = datapath.id
        source_mac = eth_header.src
        destination_mac = eth_header.dst

        # --- 1. Find Destination in our MAC table ---
        if destination_mac in self.host_location_table:
            dest_switch_id, dest_port = self.host_location_table[destination_mac]
            
            # --- 2. Check if packet is already at the destination switch ---
            if switch_id == dest_switch_id:
                # This is the last hop. Install a simple rule.
                actions = [parser.OFPActionOutput(dest_port)]
                match = parser.OFPAction(eth_dst=destination_mac)
                self.add_flow(datapath, 1, match, actions, idle_timeout=10)
                # Send this first packet on its way
                self._send_packet_out(datapath, message, actions)
                return
            
            # --- 3. Packet is not at the destination, calculate path ---
            else:
                self.logger.info(f"{Colors.CYAN}Calculating IP path: Switch {switch_id} -> Switch {dest_switch_id}{Colors.RESET}")
                
                try:
                    # --- Run Dijkstra's Algorithm ---
                    path = nx.shortest_path(self.network_graph, 
                                            source=switch_id, 
                                            target=dest_switch_id, 
                                            weight='weight')
                    self.logger.info(f"{Colors.CYAN}Shortest IP path found: {path}{Colors.RESET}")
                    
                    # --- 4. Install flow rules on all switches in the path ---
                    for i in range(len(path) - 1):
                        current_switch_id = path[i]
                        next_switch_id = path[i+1]
                        
                        # Get the correct output port from our graph
                        out_port = self.network_graph[current_switch_id][next_switch_id]['port']
                        
                        # Get the datapath object for this switch
                        current_datapath = self.get_datapath(current_switch_id) 
                        
                        if current_datapath:
                             # Match on both src and dst for a specific flow
                             match = parser.OFPMatch(eth_src=source_mac, eth_dst=destination_mac)
                             actions = [parser.OFPActionOutput(out_port)]
                             self.add_flow(current_datapath, 1, match, actions, idle_timeout=10)

                    # --- 5. Install the final hop rule (on the destination switch) ---
                    dest_datapath = self.get_datapath(dest_switch_id)
                    if dest_datapath:
                        match = parser.OFPMatch(eth_src=source_mac, eth_dst=destination_mac)
                        actions = [parser.OFPActionOutput(dest_port)] 
                        self.add_flow(dest_datapath, 1, match, actions, idle_timeout=10)

                    # --- 6. Send the original packet out the *first* hop ---
                    first_hop_port = self.network_graph[switch_id][path[1]]['port']
                    actions = [parser.OFPActionOutput(first_hop_port)]
                    self._send_packet_out(datapath, message, actions)

                except nx.NetworkXNoPath:
                    self.logger.warning(f"{Colors.RED}No IP path found from {switch_id} to {dest_switch_id}{Colors.RESET}")
        
        else:
            # We should know all hosts from our proactive ARP, so this is an error
            self.logger.warning(f"{Colors.YELLOW}Unknown IP dest MAC {destination_mac}. Dropping packet.{Colors.RESET}")


    # --- Helper Functions ---

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        """A helper function to send an OFPFlowMod message."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # Define the instruction: "Apply these actions"
        instructions = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        
        # Create the flow-mod message
        flow_mod_message = parser.OFPFlowMod(
            datapath=datapath, 
            priority=priority,
            match=match, 
            instructions=instructions,
            idle_timeout=idle_timeout,  # Remove flow if idle
            hard_timeout=hard_timeout   # Remove flow after a hard limit
        )
        datapath.send_msg(flow_mod_message)

    def _send_packet_out(self, datapath, message, actions, in_port=None, buffer_id=None, data=None):
        """A helper function to send an OFPPacketOut message."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # Determine if this is a packet we're forwarding or a new one
        if message: # If this is for an existing PacketIn
            in_port = message.match['in_port']
            buffer_id = message.buffer_id
            if buffer_id == ofproto.OFP_NO_BUFFER:
                data = message.data
        else: # If this is a new, self-generated packet
            in_port = ofproto.OFPP_CONTROLLER
            buffer_id = ofproto.OFP_NO_BUFFER

        # Create and send the PacketOut message
        out = parser.OFPPacketOut(
            datapath=datapath, 
            buffer_id=buffer_id,
            in_port=in_port, 
            actions=actions, 
            data=data
        )
        datapath.send_msg(out)

    def get_datapath(self, switch_id):
        """A safe helper to get the datapath object from our list."""
        return self.active_switches.get(switch_id)
