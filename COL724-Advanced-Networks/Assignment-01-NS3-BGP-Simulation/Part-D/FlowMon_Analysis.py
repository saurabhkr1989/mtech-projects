import xml.etree.ElementTree as ET
import sys
import os

def parse_flowmon_xml(filename="PartD-Results.xml"):
   
   if not os.path.exists(filename):
        print(f"Error: The file '{filename}' was not found. Please run the simulation first.")
        return
    try:
        tree = ET.parse(filename)
        root = tree.getroot()
    except ET.ParseError:
        print(f"Error: Could not parse '{filename}'. It may be empty or malformed.")
        return

    flow_classifiers = {}
    try:
        classifier_root = root.find('Ipv4FlowClassifier')
        for flow in classifier_root.findall('Flow'):
            flow_id = flow.get('flowId')
            flow_classifiers[flow_id] = {
                "source": flow.get('sourceAddress'), "dest": flow.get('destinationAddress'),
                "sport": flow.get('sourcePort'), "dport": flow.get('destinationPort'),
                "protocol": flow.get('protocol')
            }
    except AttributeError:
        print("Error: Could not find 'Ipv4FlowClassifier' tag in the XML.")
        return

    flow_stats_root = root.find('FlowStats')
    
    grand_total_tx_packets = 0
    grand_total_rx_packets = 0
    
    print("\n--- Detailed Flow Analysis ---")

    for flow in flow_stats_root.findall('Flow'):
        flow_id = flow.get('flowId')
        
        if flow_id not in flow_classifiers:
            continue

        classifier = flow_classifiers[flow_id]
        
        try:
            tx_packets = int(flow.get('txPackets'))
            rx_packets = int(flow.get('rxPackets'))
            
            # --- NEW: Accumulate grand totals ---
            grand_total_tx_packets += tx_packets
            grand_total_rx_packets += rx_packets

            # (The rest of the calculations for the per-flow report)
            tx_bytes = int(flow.get('txBytes'))
            rx_bytes = int(flow.get('rxBytes'))
            time_first_tx_ns = float(flow.get('timeFirstTxPacket')[:-2].replace('+', ''))
            time_last_tx_ns = float(flow.get('timeLastTxPacket')[:-2].replace('+', ''))
            time_first_rx_ns = float(flow.get('timeFirstRxPacket')[:-2].replace('+', ''))
            time_last_rx_ns = float(flow.get('timeLastRxPacket')[:-2].replace('+', ''))
            delay_sum_ns = float(flow.get('delaySum')[:-2].replace('+', ''))
            lost_packets = tx_packets - rx_packets
            loss_ratio = (lost_packets / tx_packets) if tx_packets > 0 else 0.0
            avg_delay_ms = (delay_sum_ns / rx_packets / 1e6) if rx_packets > 0 else 0.0
            tx_duration_s = (time_last_tx_ns - time_first_tx_ns) / 1e9
            tx_bitrate_kbps = (tx_bytes * 8) / tx_duration_s / 1000 if tx_duration_s > 0 else 0.0
            rx_duration_s = (time_last_rx_ns - time_first_rx_ns) / 1e9
            rx_bitrate_kbps = (rx_bytes * 8) / rx_duration_s / 1000 if rx_duration_s > 0 else 0.0
            protocol = "UDP" if classifier.get('protocol') == "17" else "TCP"

            print(f"\nFlowID: {flow_id} ({protocol} {classifier['source']}/{classifier['sport']} --> {classifier['dest']}/{classifier['dport']})")
            print(f"\tTX Bitrate: {tx_bitrate_kbps:.2f} kbit/s")
            print(f"\tRX Bitrate: {rx_bitrate_kbps:.2f} kbit/s")
            print(f"\tMean Delay: {avg_delay_ms:.2f} ms")
            print(f"\tPacket Loss Ratio: {loss_ratio:.2%}")

        except (ValueError, TypeError, KeyError, ZeroDivisionError) as e:
            print(f"\nCould not process FlowID {flow_id}. Error: {e}")
            
    grand_total_lost = grand_total_tx_packets - grand_total_rx_packets
    overall_loss_ratio = (grand_total_lost / grand_total_tx_packets) if grand_total_tx_packets > 0 else 0.0
    
    print("\n\n--- Overall Network Totals ---")
    print("------------------------------------")
    print(f"Total Packets Transmitted: {grand_total_tx_packets}")
    print(f"Total Packets Received:    {grand_total_rx_packets}")
    print(f"Total Packets Lost:        {grand_total_lost}")
    print(f"Overall Packet Loss Ratio: {overall_loss_ratio:.2%}")
    print("------------------------------------")


if __name__ == '__main__':
    parse_flowmon_xml()
