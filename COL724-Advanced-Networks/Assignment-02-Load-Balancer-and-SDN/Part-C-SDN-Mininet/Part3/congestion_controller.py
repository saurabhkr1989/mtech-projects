# p4_ca_spr.py - Congestion-Aware Shortest Path Routing Controller
#
# This Ryu controller is the "brain" for the software-defined network.
# It evolves from a simple L2 learning switch to a smart, traffic-engineering controller.
#
# --- How it Works ---
# 1. L2 Learning: It learns the location of hosts (which switch and port they are on)
#    as they send traffic, just like a basic switch.
#
# 2. Shortest Path Routing: When a new flow needs to be established between hosts
#    on different switches, it calculates the shortest path through the network graph.
#
# 3. Congestion Awareness (The Smart Part):
#    - A background thread constantly polls the switches for traffic statistics (bytes sent).
#    - It calculates the real-time utilization (load) of each inter-switch link.
#    - It dynamically adjusts the "cost" (weight) of traversing each link. A busy link
#      becomes more "expensive" to use.
#    - Therefore, when `shortest_path` is calculated, it automatically finds the path
#      that is not just notionally shortest, but is *currently the least congested*.

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib.packet import packet, ethernet, ether_types
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event

import networkx as nx
from ryu.lib import hub
from collections import defaultdict
import time
from operator import attrgetter


class CongestionAwareController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    # How often (in seconds) to ask switches for their traffic stats.
    POLL_INTERVAL = 5
    
    # This factor determines how much link utilization affects path selection.
    # A higher value makes the controller react more aggressively to congestion,
    # treating a busy link as much "longer" or more "costly" to traverse.
    # Formula: new_weight = static_weight + (UTILIZATION_PENALTY * utilization)
    UTILIZATION_PENALTY = 10.0

    def __init__(self, *args, **kwargs):
        super(CongestionAwareController, self).__init__(*args, **kwargs)
        
        # --- ANSI Color Codes for Logging ---
        self.RESET = '\033[0m'
        self.GREEN = '\033[92m'
        self.YELLOW = '\033[93m'
        self.BLUE = '\033[94m'
        self.CYAN = '\033[96m'
        
        # --- Core Data Structures ---
        # A dictionary to remember where hosts are. {mac_addr -> (switch_dpid, port_no)}
        self.mac_to_port = {}
        # Our "mental map" of the network, represented as a graph.
        self.net = nx.DiGraph()
        # A dictionary to keep track of connected switches. {dpid -> datapath_object}
        self.datapaths = {}

        # --- Congestion Monitoring Data Structures ---
        # Stores the last reading of transmitted bytes. {dpid: {port_no: tx_bytes}}
        self.port_stats = defaultdict(lambda: defaultdict(int))
        # Stores the maximum link speed in bits/sec. {dpid: {port_no: speed_bps}}
        self.port_speed = defaultdict(lambda: defaultdict(int))
        # Stores the timestamp of the last stat poll. {dpid: {port_no: timestamp}}
        self.last_poll_time = defaultdict(lambda: defaultdict(float))
        # Stores the calculated utilization (0.0 to 1.0). {dpid: {port_no: utilization}}
        self.link_utilization = defaultdict(lambda: defaultdict(float))
        
        # --- Start the Brain's Background Task ---
        # This greenlet will run in the background, continuously monitoring the network.
        self.monitor_thread = hub.spawn(self._monitor)

    def _build_static_topology(self):
        """
        Builds the controller's initial, static "map" of the network.
        This is hard-coded to match the 'p3_topo.py' script. It defines
        the switches, their connections, and the maximum bandwidth of each link.
        This base map is crucial for later calculating link utilization.
        """
        # Add the four switches as nodes in our graph.
        for dpid in range(1, 5):
            self.net.add_node(dpid)

        mbps_to_bps = 1000 * 1000

        # --- Host-facing Port Speeds ---
        # Record the speed of the ports connected to hosts.
        self.port_speed[1][1] = 2.0 * mbps_to_bps
        self.port_speed[2][1] = 2.0 * mbps_to_bps
        self.port_speed[3][1] = 2.0 * mbps_to_bps
        self.port_speed[4][1] = 2.0 * mbps_to_bps
        
        # --- Inter-Switch Links & Speeds ---
        # Here we define the connections between switches. For each link, we add two
        # directed edges to our graph (one for each direction) and record the port speeds.
        # The initial 'weight' is the inverse of the bandwidth (1/bw). This means
        # higher bandwidth links have a lower initial weight, making them "shorter" paths.
        
        # Link s1 <-> s2 (Bandwidth: 2 Mbps)
        bw_s1_s2 = 2.0 * mbps_to_bps
        self.net.add_edge(1, 2, port=2, weight=1.0/2.0)
        self.port_speed[1][2] = bw_s1_s2
        self.net.add_edge(2, 1, port=2, weight=1.0/2.0)
        self.port_speed[2][2] = bw_s1_s2

        # Link s2 <-> s3 (Bandwidth: 2 Mbps)
        bw_s2_s3 = 2.0 * mbps_to_bps
        self.net.add_edge(2, 3, port=3, weight=1.0/2.0)
        self.port_speed[2][3] = bw_s2_s3
        self.net.add_edge(3, 2, port=2, weight=1.0/2.0)
        self.port_speed[3][2] = bw_s2_s3
        
        # Link s3 <-> s4 (Bandwidth: 1 Mbps)
        bw_s3_s4 = 1.0 * mbps_to_bps
        self.net.add_edge(3, 4, port=3, weight=1.0/1.0)
        self.port_speed[3][3] = bw_s3_s4
        self.net.add_edge(4, 3, port=2, weight=1.0/1.0)
        self.port_speed[4][2] = bw_s3_s4
        
        # Link s4 <-> s1 (Bandwidth: 1 Mbps)
        bw_s4_s1 = 1.0 * mbps_to_bps
        self.net.add_edge(4, 1, port=3, weight=1.0/1.0)
        self.port_speed[4][3] = bw_s4_s1
        self.net.add_edge(1, 4, port=3, weight=1.0/1.0)
        self.port_speed[1][3] = bw_s4_s1
        
        self.logger.info(f"{self.GREEN}✔️  Static network topology and port speeds loaded.{self.RESET}")

    # --- Congestion Monitoring Core Logic ---

    def _monitor(self):
        """
        The main loop for the background monitoring thread.
        It periodically wakes up and asks all connected switches for their stats.
        """
        self.logger.info(f"{self.BLUE}Started congestion monitoring thread (Polls every {self.POLL_INTERVAL} sec){self.RESET}")
        while True:
            # We iterate over a copy of the keys to avoid dictionary size change errors
            # if a switch connects or disconnects during the loop.
            for dpid in list(self.datapaths.keys()):
                dp = self.get_datapath(dpid)
                if dp:
                    self._request_port_stats(dp)
            hub.sleep(self.POLL_INTERVAL)

    def _request_port_stats(self, datapath):
        """Sends an OpenFlow Port Statistics Request message to a single switch."""
        parser = datapath.ofproto_parser
        req = parser.OFPPortStatsRequest(datapath, 0, datapath.ofproto.OFPP_ANY)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """
        Handles the reply from a switch containing port statistics.
        This is where the magic happens: we calculate link utilization and then
        trigger an update of our network graph's link weights.
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        
        for stat in sorted(body, key=attrgetter('port_no')):
            if stat.port_no == ofproto_v1_3.OFPP_LOCAL:
                continue

            current_time = time.time()
            last_time = self.last_poll_time[dpid][stat.port_no]
            last_bytes = self.port_stats[dpid][stat.port_no]
            
            # If we have a previous data point, we can calculate the rate.
            if last_time > 0:
                time_delta = current_time - last_time
                bytes_delta = stat.tx_bytes - last_bytes
                
                if time_delta > 0:
                    # Calculate speed in bits per second (bps).
                    bps = (bytes_delta * 8.0) / time_delta
                    max_bps = self.port_speed.get(dpid, {}).get(stat.port_no)
                    
                    if max_bps:
                        # Utilization is the current speed as a fraction of the maximum speed.
                        utilization = max(0.0, min(1.0, bps / max_bps)) # Clamp between 0 and 1
                        self.link_utilization[dpid][stat.port_no] = utilization
                        # --- EDIT: Added this log line back as INFO ---
                        self.logger.info(f"{self.CYAN}Switch {dpid} Port {stat.port_no}: {utilization * 100:.2f}% utilization{self.RESET}")
                    else:
                        self.link_utilization[dpid][stat.port_no] = 0.0

            # Store the current stats to use as the "last" stats in the next interval.
            self.port_stats[dpid][stat.port_no] = stat.tx_bytes
            self.last_poll_time[dpid][stat.port_no] = current_time
        
        # After processing all stats from this switch, update the network graph.
        self._update_link_weights()

    def _update_link_weights(self):
        """
        Recalculates the 'weight' for every link in the network graph.
        The new weight is a combination of the link's static capacity and its
        current, dynamic utilization.
        """
        # --- EDIT: Changed from DEBUG to INFO ---
        self.logger.info(f"{self.CYAN}Updating link weights in graph...{self.RESET}")
        for u, v, data in self.net.edges(data=True):
            port_no = data['port']
            
            # Start with the static weight (based on max bandwidth).
            max_bw_mbps = self.port_speed.get(u, {}).get(port_no, 0) / (1000.0 * 1000.0)
            static_weight = 1.0 / max_bw_mbps if max_bw_mbps > 0 else float('inf')

            # Get the current utilization for this link's egress port.
            utilization = self.link_utilization.get(u, {}).get(port_no, 0.0)
            
            # Calculate the dynamic penalty based on how busy the link is.
            dynamic_penalty = self.UTILIZATION_PENALTY * utilization
            
            # The new weight is the base cost plus the congestion penalty.
            new_weight = static_weight + dynamic_penalty
            
            self.net[u][v]['weight'] = new_weight
            # --- EDIT: Changed from DEBUG to INFO ---
            self.logger.info(
                f"{self.CYAN}  -> Link {u}->{v} (Port {port_no}): Util={utilization * 100:.2f}%, New_Weight={new_weight:.2f}{self.RESET}"
            )

    # --- Standard Ryu Event Handlers ---

    @set_ev_cls(event.EventSwitchEnter, [MAIN_DISPATCHER, CONFIG_DISPATCHER])
    def _switch_enter_handler(self, ev):
        """Handles a switch connecting to the controller."""
        datapath = ev.switch.dp
        self.datapaths[datapath.id] = datapath
        self.logger.info(f"{self.GREEN}Switch {datapath.id} connected.{self.RESET}")

    @set_ev_cls(event.EventSwitchLeave, [MAIN_DISPATCHER, CONFIG_DISPATCHER])
    def _switch_leave_handler(self, ev):
        """Handles a switch disconnecting from the controller."""
        datapath = ev.switch.dp
        if datapath.id in self.datapaths:
            del self.datapaths[datapath.id]
            self.logger.info(f"{self.YELLOW}Switch {datapath.id} disconnected.{self.RESET}")

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """Handles the initial handshake with a switch."""
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        
        # If this is the first switch connecting, build our network map.
        if not self.net.nodes():
            self._build_static_topology()

        # Install a default "table-miss" flow entry.
        # This rule says: "If a packet arrives and doesn't match any other rule,
        # send it to the controller for instructions."
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 0, match, actions)

    def add_flow(self, datapath, priority, match, actions, idle_timeout=0, hard_timeout=0):
        """A helper function to simplify adding flow entries to a switch."""
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = parser.OFPFlowMod(datapath=datapath, priority=priority,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout,
                                match=match, instructions=inst)
        datapath.send_msg(mod)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        """
        The main packet processing logic. This is called whenever a switch sends
        a packet to the controller (due to the table-miss rule).
        """
        msg = ev.msg
        datapath = msg.datapath
        dpid = datapath.id
        in_port = msg.match['in_port']
        parser = datapath.ofproto_parser

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]

        # Ignore LLDP packets, which are used for topology discovery.
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return
            
        src = eth.src
        dst = eth.dst

        # --- Step 1: Learn the source host's location ---
        if src not in self.mac_to_port:
            self.mac_to_port[src] = (dpid, in_port)
            self.logger.info(f"{self.GREEN}Learned: Host {src} is on Switch {dpid}, Port {in_port}{self.RESET}")

        # --- Step 2: Determine the destination and find a path ---
        if dst in self.mac_to_port:
            dst_dpid, dst_port = self.mac_to_port[dst]
            
            # Create a specific match for this exact source-destination flow.
            match = parser.OFPMatch(eth_src=src, eth_dst=dst)
            
            # CASE A: Source and Destination are on the same switch.
            if dpid == dst_dpid:
                actions = [parser.OFPActionOutput(dst_port)]
                # --- FIX --- Add hard_timeout to force re-evaluation
                self.add_flow(datapath, 1, match, actions, idle_timeout=10, hard_timeout=10)
                # Send the packet out immediately.
                out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                          in_port=in_port, actions=actions, data=msg.data)
                datapath.send_msg(out)
                return
            
            # CASE B: Source and Destination are on different switches.
            else:
                self.logger.info(f"{self.BLUE}Calculating path for {src} -> {dst} (Switch {dpid} to {dst_dpid})...{self.RESET}")
                try:
                    # This is the key call: it finds the shortest path using our
                    # dynamically updated, congestion-aware link weights.
                    path = nx.shortest_path(self.net, source=dpid, target=dst_dpid, weight='weight')
                    self.logger.info(f"{self.GREEN}Path found: {path}{self.RESET}")
                    
                    # --- Step 3: Install flow rules along the entire path ---
                    # For each hop in the path, install a rule on that switch.
                    for i in range(len(path) - 1):
                        current_switch = path[i]
                        next_switch = path[i+1]
                        out_port = self.net[current_switch][next_switch]['port']
                        dp = self.get_datapath(current_switch)
                        if dp:
                            actions = [parser.OFPActionOutput(out_port)]
                            # --- FIX --- Add hard_timeout to force re-evaluation
                            self.add_flow(dp, 1, match, actions, idle_timeout=10, hard_timeout=10)

                    # Install the final rule on the destination switch to reach the host.
                    dp = self.get_datapath(dst_dpid)
                    if dp:
                        actions = [parser.OFPActionOutput(dst_port)]
                        # --- FIX --- Add hard_timeout to force re-evaluation
                        self.add_flow(dp, 1, match, actions, idle_timeout=10, hard_timeout=10)

                    # Send the original packet on its way down the new path.
                    first_hop_port = self.net[dpid][path[1]]['port']
                    actions = [parser.OFPActionOutput(first_hop_port)]
                    out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                              in_port=in_port, actions=actions, data=msg.data)
                    datapath.send_msg(out)

                except nx.NetworkXNoPath:
                    self.logger.warning(f"{self.YELLOW}⚠️ No path found from {dpid} to {dst_dpid}. Flooding packet instead.{self.RESET}")
                    self._flood(datapath, msg, in_port)

        # --- Step 4: If destination is unknown, flood the packet ---
        else:
            self._flood(datapath, msg, in_port)

    def _flood(self, datapath, msg, in_port):
        """
        Floods a packet intelligently. Instead of just sending the packet out all
        ports, it installs a short-lived flow rule to handle subsequent packets
        of the same type (e.g., ARP requests). This prevents the controller from
        being overwhelmed by broadcast storms.
        """
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        
        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        
        # Match on the unknown destination MAC to group similar flood requests.
        match = parser.OFPMatch(in_port=in_port, eth_dst=eth.dst)

        # Install a temporary rule: "For the next 5 seconds, if you see a packet
        # like this, just flood it yourself. Don't ask me again."
        self.add_flow(datapath, 1, match, actions, idle_timeout=5, hard_timeout=10)

        # Send this first packet out using a PacketOut message.
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=in_port, actions=actions, data=msg.data)
        datapath.send_msg(out)

    def get_datapath(self, dpid):
        """A helper to safely retrieve a datapath object."""
        return self.datapaths.get(dpid)

