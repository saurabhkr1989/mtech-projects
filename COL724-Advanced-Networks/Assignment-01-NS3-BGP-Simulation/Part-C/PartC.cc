#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/netanim-module.h"
#include "ns3/ipv4-static-routing-helper.h"
#include "ns3/ipv4-list-routing-helper.h"

using namespace ns3;

// Network Topology
//
//          (AS2)
//           r1
//          /  \ (10Mbps/5ms)
// (AS1) r0 ---- r2 (AS3)
//        \----/
//      (100Mbps/1ms)
//
// Policy: Force traffic from r0 to r2 via r1

NS_LOG_COMPONENT_DEFINE ("BGP-lite_PartC");

int main (int argc, char *argv[])
{
  Time::SetResolution (Time::NS);
  CommandLine cmd;
  cmd.Parse (argc, argv);

  LogComponentEnable ("BGP-lite_PartC", LOG_LEVEL_INFO);
  LogComponentEnable ("UdpEchoClientApplication", LOG_LEVEL_INFO);
  LogComponentEnable ("UdpEchoServerApplication", LOG_LEVEL_INFO);

  NS_LOG_INFO ("Part B : BGP-lite Simulation by forcing path via AS2");

  NodeContainer routers;
  routers.Create (3);
  Ptr<Node> r0 = routers.Get (0);
  Ptr<Node> r1 = routers.Get (1);
  Ptr<Node> r2 = routers.Get (2);

  // list routing helper to combine static routing
  Ipv4ListRoutingHelper listRouting;
  Ipv4StaticRoutingHelper staticRouting;
  
  // static routing as the highest priority
  listRouting.Add (staticRouting, 0);

  InternetStackHelper internet;
  internet.SetRoutingHelper (listRouting); 
  internet.Install (routers);

  PointToPointHelper p2p;
  p2p.SetDeviceAttribute ("DataRate", StringValue ("10Mbps"));
  p2p.SetChannelAttribute ("Delay", StringValue ("5ms"));
  NetDeviceContainer d01 = p2p.Install (r0, r1);
  NetDeviceContainer d12 = p2p.Install (r1, r2);

  PointToPointHelper p2p_direct;
  p2p_direct.SetDeviceAttribute ("DataRate", StringValue ("100Mbps"));
  p2p_direct.SetChannelAttribute ("Delay", StringValue ("1ms"));
  NetDeviceContainer d02 = p2p_direct.Install (r0, r2);

  Ipv4AddressHelper ipv4;
  ipv4.SetBase ("10.0.1.0", "255.255.255.0");
  Ipv4InterfaceContainer i01 = ipv4.Assign (d01);

  ipv4.SetBase ("10.0.2.0", "255.255.255.0");
  Ipv4InterfaceContainer i12 = ipv4.Assign (d12);

  ipv4.SetBase ("10.0.3.0", "255.255.255.0");
  Ipv4InterfaceContainer i02 = ipv4.Assign (d02);

  // Static Routing
  //NS_LOG_INFO("Configuring Static Routes to enforce policy...");

  Ptr<Ipv4StaticRouting> staticRouting_r0 = staticRouting.GetStaticRouting (r0->GetObject<Ipv4> ());
  Ptr<Ipv4StaticRouting> staticRouting_r2 = staticRouting.GetStaticRouting (r2->GetObject<Ipv4> ());

  staticRouting_r0->AddNetworkRouteTo (Ipv4Address ("10.0.2.0"), Ipv4Mask ("255.255.255.0"), i01.GetAddress (1), 1);

  staticRouting_r2->AddNetworkRouteTo (Ipv4Address ("10.0.1.0"), Ipv4Mask ("255.255.255.0"), i12.GetAddress (0), 1);

  
  // Ipv4GlobalRoutingHelper::PopulateRoutingTables (); // Replaced by  static routes

  uint16_t port = 9;
  UdpEchoServerHelper server (port);
  ApplicationContainer apps = server.Install (r2); 
  apps.Start (Seconds (1.0));
  apps.Stop (Seconds (10.0));

  UdpEchoClientHelper client (i12.GetAddress (1), port);
  client.SetAttribute ("MaxPackets", UintegerValue (5));
  client.SetAttribute ("Interval", TimeValue (Seconds (1.0)));
  client.SetAttribute ("PacketSize", UintegerValue (1024));
  apps = client.Install (r0); 
  apps.Start (Seconds (2.0));
  apps.Stop (Seconds (10.0));

  FlowMonitorHelper flowmon;
  Ptr<FlowMonitor> monitor = flowmon.InstallAll ();

  // Set positions for better visualization in NetAnim
  AnimationInterface anim("PartC-results-anim.xml");

  anim.SetConstantPosition(r0, 10.0, 50.0);
  anim.SetConstantPosition(r1, 50.0, 20.0);
  anim.SetConstantPosition(r2, 90.0, 50.0);

  Simulator::Stop (Seconds(10.0));
  Simulator::Run ();

  monitor->SerializeToXmlFile("PartC-results.xml", true, true);

  Simulator::Destroy ();
  //NS_LOG_INFO ("Simulation finished.");
  return 0;
}

