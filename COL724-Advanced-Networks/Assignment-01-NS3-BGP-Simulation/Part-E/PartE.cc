#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/netanim-module.h"
#include "ns3/ipv4-global-routing-helper.h"
#include <sstream>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("PartE");

void InterfaceDown(Ptr<Node> node, uint32_t interfaceIndex)
{
    Ptr<Ipv4> ipv4 = node->GetObject<Ipv4>();
    if (ipv4 && ipv4->GetNInterfaces() > interfaceIndex)
    {
        ipv4->SetDown(interfaceIndex);
        NS_LOG_UNCOND("Time: " << Simulator::Now().GetSeconds() << "s\t Bringing Down Interface " << interfaceIndex << " on Node " << node->GetId());
    }
}

void InterfaceUp(Ptr<Node> node, uint32_t interfaceIndex)
{
    Ptr<Ipv4> ipv4 = node->GetObject<Ipv4>();
    if (ipv4 && ipv4->GetNInterfaces() > interfaceIndex)
    {
        ipv4->SetUp(interfaceIndex);
        NS_LOG_UNCOND("Time : " << Simulator::Now().GetSeconds() << "s\t Restoring Interface " << interfaceIndex << " on Node " << node->GetId());
    }
}

void RecomputeRoutingTables()
{
    NS_LOG_UNCOND("Time : " << Simulator::Now().GetSeconds() << "s\t Recomputing Global Static Routing Tables (Convergence Delay : 01 Secs)");
    Ipv4GlobalRoutingHelper::RecomputeRoutingTables();
}

int main(int argc, char* argv[])
{
    double simulationTime = 15.0;
    double linkFailureTime = 5.0;
    double linkRecoveryTime = 7.0;
    double convergenceDelay = 1.0;
    std::string flowmon_filename = "PartE-Results.xml";

    LogComponentEnable("UdpEchoClientApplication", LOG_LEVEL_INFO);
    LogComponentEnable("UdpEchoServerApplication", LOG_LEVEL_INFO);
    
    NodeContainer routers, hosts;
    routers.Create(4); // CHANGED: 4 routers: AS1, AS2, AS3, AS4 (Nodes 0, 1, 2, 3)
    hosts.Create(2);   // Client, Server (Nodes 4, 5)

    InternetStackHelper stack;
    stack.Install(routers);
    stack.Install(hosts);

    PointToPointHelper p2p_primary;
    p2p_primary.SetDeviceAttribute("DataRate", StringValue("10Mbps"));
    p2p_primary.SetChannelAttribute("Delay", StringValue("5ms")); // Lower delay for priority

    PointToPointHelper p2p_backup;
    p2p_backup.SetDeviceAttribute("DataRate", StringValue("10Mbps"));
    p2p_backup.SetChannelAttribute("Delay", StringValue("10ms"));

    Ipv4AddressHelper address;
    // Client (Node 4) to AS1 (Node 0)
    address.SetBase("10.1.1.0", "255.255.255.0");
    address.Assign(p2p_primary.Install(hosts.Get(0), routers.Get(0)));
    // Server (Node 5) to AS3 (Node 2)
    address.SetBase("10.1.2.0", "255.255.255.0");
    Ipv4InterfaceContainer i_h3_as3 = address.Assign(p2p_primary.Install(hosts.Get(1), routers.Get(2)));
    
    // Path A (Primary): AS1 -> AS2 -> AS3
    address.SetBase("10.0.1.0", "255.255.255.0"); // AS1-AS2 link
    address.Assign(p2p_primary.Install(routers.Get(0), routers.Get(1)));
    address.SetBase("10.0.2.0", "255.255.255.0"); // AS2-AS3 link (This one will fail)
    address.Assign(p2p_primary.Install(routers.Get(1), routers.Get(2)));

    // Path B (Backup): AS1 -> AS4 -> AS3
    address.SetBase("10.0.3.0", "255.255.255.0"); // AS1-AS4 link
    address.Assign(p2p_backup.Install(routers.Get(0), routers.Get(3)));
    address.SetBase("10.0.4.0", "255.255.255.0"); // AS4-AS3 link
    address.Assign(p2p_backup.Install(routers.Get(3), routers.Get(2)));

    NS_LOG_UNCOND("Time: 0.0s\t Populating Initial Global Static Routing Tables");
    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    uint16_t port = 9;
    UdpEchoServerHelper echoServer(port);
    ApplicationContainer serverApps = echoServer.Install(hosts.Get(1));
    serverApps.Start(Seconds(1.0));
    serverApps.Stop(Seconds(simulationTime - 1.0));

    UdpEchoClientHelper echoClient(i_h3_as3.GetAddress(0), port);
    echoClient.SetAttribute("MaxPackets", UintegerValue(100));
    echoClient.SetAttribute("Interval", TimeValue(Seconds(1.0)));
    echoClient.SetAttribute("PacketSize", UintegerValue(1024));
    ApplicationContainer clientApps = echoClient.Install(hosts.Get(0));
    clientApps.Start(Seconds(2.0));
    clientApps.Stop(Seconds(simulationTime - 1.0));

    // --- Scheduled Link Failure (AS2-AS3 Link) ---
    uint32_t as2_fail_interface = 2; // On AS2 (Node 1), link to AS3 is the 2nd interface
    uint32_t as3_fail_interface = 2; // On AS3 (Node 2), link to AS2 is the 2nd interface
    Simulator::Schedule(Seconds(linkFailureTime), &InterfaceDown, routers.Get(1), as2_fail_interface);
    Simulator::Schedule(Seconds(linkFailureTime), &InterfaceDown, routers.Get(2), as3_fail_interface);
    Simulator::Schedule(Seconds(linkFailureTime + convergenceDelay), &RecomputeRoutingTables);
    Simulator::Schedule(Seconds(linkRecoveryTime), &InterfaceUp, routers.Get(1), as2_fail_interface);
    Simulator::Schedule(Seconds(linkRecoveryTime), &InterfaceUp, routers.Get(2), as3_fail_interface);
    Simulator::Schedule(Seconds(linkRecoveryTime + convergenceDelay), &RecomputeRoutingTables);

    AnimationInterface anim("PartE-Results-Animation.xml");
    
    anim.SetConstantPosition(hosts.Get(0), 0, 40);
    anim.SetConstantPosition(routers.Get(0), 20, 40);
    anim.SetConstantPosition(routers.Get(1), 40, 20); // AS2 (Top Path)
    anim.SetConstantPosition(routers.Get(3), 40, 60); // AS4 (Bottom Path)
    anim.SetConstantPosition(routers.Get(2), 60, 40); // AS3
    anim.SetConstantPosition(hosts.Get(1), 80, 40);

    NodeContainer allNodes = NodeContainer(routers, hosts);
    std::string node_names[] = {"AS1", "AS2", "AS3", "AS4", "Client", "Server"};
    
    for (uint32_t i = 0; i < allNodes.GetN(); ++i)
    {
        Ptr<Node> node = allNodes.Get(i);
        Ptr<Ipv4> ipv4 = node->GetObject<Ipv4>();
        std::stringstream ss;
        ss << node_names[i] << ":";
        
        for (uint32_t j = 1; j < ipv4->GetNInterfaces(); ++j)
        {
            ss << "\n" << ipv4->GetAddress(j, 0).GetLocal();
        }
        anim.UpdateNodeDescription(node, ss.str());
    }

    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor = flowmon.InstallAll();
    
    Simulator::Stop(Seconds(simulationTime));
    Simulator::Run();
    NS_LOG_INFO("Simulation Finished.");

    monitor->SerializeToXmlFile(flowmon_filename, true, true);
    
    Simulator::Destroy();
    return 0;
}
