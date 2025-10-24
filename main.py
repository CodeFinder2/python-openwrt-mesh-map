#!/usr/bin/env python3
# Tested with Python 3.8+ and OpenWrt 24.10.4 (as of 24/10/2025). Requires 'opkg install iperf3'.

import re
import paramiko
import networkx as nx
import matplotlib.pyplot as plt
import json
import time
import socket

# Configuration
from mesh_nodes import mesh_nodes

# ⚙️ Options
ENABLE_IPERF3_TESTS = False   # → True = iperf3 measurement active
IPERF_DURATION = 5           # Duration of iperf3 test in seconds

mac_ip_map = {}        # mac → ip

def dbm_to_percent(dbm):
    try:
        return max(0, min(100, 2 * (int(dbm) + 100)))
    except:
        return None

def run_ssh_command(host, user, password, command):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password)
    stdin, stdout, stderr = client.exec_command(command)
    output = stdout.read().decode()
    client.close()
    return output

def run_iperf3_test(ap1_name, ap2_name, node1, node2, counter):
    """
    Performs an iperf3 test between two OpenWrt routers.
    Returns (throughput_mbps, latency_ms) or (None, None) on errors.
    """
    ip_client = node1['ip']
    ip_server = node2['ip']
    user_client = node1['user']
    pass_client = node1['password']
    user_server = node2['user']
    pass_server = node2['password']

    print(f"[INFO] Starting iperf3 test {ap1_name} → {ap2_name} ({counter}/{int((len(mesh_nodes) * (len(mesh_nodes)-1))/2)})...")

    try:
        # Start iperf3 server on target (single test, no nohup needed)
        run_ssh_command(
            ip_server, user_server, pass_server,
            "pkill iperf3; (iperf3 -s -1 > /tmp/iperf3.log 2>&1 &)"
        )
        time.sleep(2)  # Give time to start

        # Start iperf3 client (JSON output)
        cmd_client = f"iperf3 -c {ip_server} -J -t 5"
        out = run_ssh_command(ip_client, user_client, pass_client, cmd_client)

        if not out.strip():
            print(f"[WARN] No output from iperf3 client {ap1_name} → {ap2_name}")
            return None, None

        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            print(f"[DEBUG] Could not parse iperf3 output as JSON:\n{out}")
            return None, None

        # Check for errors
        if "error" in data:
            print(f"[WARN] iperf3 error {ap1_name} → {ap2_name}: {data['error']}")
            return None, None

        # Determine throughput
        throughput = None
        if "end" in data and "sum_received" in data["end"]:
            throughput = data["end"]["sum_received"].get("bits_per_second", 0) / 1e6
        elif "end" in data and "sum" in data["end"]:
            throughput = data["end"]["sum"].get("bits_per_second", 0) / 1e6
        else:
            print(f"[DEBUG] No throughput found, iperf output:\n{out}")
            return None, None

        # Ping for rough latency estimation
        print(f"[INFO] Starting ping test {ap1_name} → {ap2_name}...")
        ping_out = run_ssh_command(ip_client, user_client, pass_client, f"ping -c 3 {ip_server}")

        latency_match = re.search(r"round-trip min/avg/max = [\d\.]+/([\d\.]+)/[\d\.]+ ms", ping_out)
        latency = float(latency_match.group(1)) if latency_match else None

        print(f"[INFO] Benchmark {ap1_name} → {ap2_name}: {throughput:.2f} Mbit/s, {latency or '?'} ms")

        return throughput, latency

    except Exception as e:
        print(f"[WARN] iperf3 test {ap1_name} → {ap2_name} failed: {e}")
        return None, None


def get_interfaces(ip, user, password):
    output = run_ssh_command(ip, user, password, "iw dev | grep Interface")
    return [line.split()[-1] for line in output.strip().split('\n') if line]

def get_clients(ip, user, password):
    clients = []
    interfaces = get_interfaces(ip, user, password)
    for iface in interfaces:
        if "mesh" in iface:
            continue
        output = run_ssh_command(ip, user, password, f"iw dev {iface} station dump")
        mac, signal = None, None
        for line in output.splitlines():
            if line.startswith("Station"):
                if mac:
                    clients.append({'mac': mac, 'signal': signal})
                mac = line.split()[1]
                signal = None
            elif re.match(r'^\s*signal:\s+-?\d+', line):
                match = re.search(r'signal:\s*(-?\d+)', line)
                if match:
                    signal = int(match.group(1))
        if mac:
            clients.append({'mac': mac, 'signal': signal})

    # Collect MAC ↔ IP mapping
    arp_output = run_ssh_command(ip, user, password, "ip neigh show")
    for line in arp_output.strip().split('\n'):
        parts = line.strip().split()
        if len(parts) >= 5 and parts[0].count('.') == 3:
            ip_addr = parts[0]
            mac_addr = parts[4].lower()
            mac_ip_map[mac_addr] = ip_addr
    return clients

def get_mesh_links(ip, user, password):
    links = []
    interfaces = get_interfaces(ip, user, password)
    for iface in interfaces:
        if "mesh" not in iface:
            continue
        output = run_ssh_command(ip, user, password, f"iw dev {iface} station dump")
        remote_mac, signal = None, None
        for line in output.splitlines():
            if line.startswith("Station"):
                remote_mac = line.split()[1]
                signal = None
            elif re.match(r'^\s*signal:\s+-?\d+', line):
                match = re.search(r'signal:\s*(-?\d+)', line)
                if match:
                    signal = int(match.group(1))
            elif remote_mac and signal:
                links.append({'remote_mac': remote_mac, 'signal': signal})
                remote_mac, signal = None, None
    return links

def get_dhcp_leases(ip, user, password):
    try:
        output = run_ssh_command(ip, user, password, "cat /tmp/dhcp.leases")
    except Exception as e:
        print(f"[WARN] Could not read DHCP leases on {ip}: {e}")
        return {}
    leases = {}
    for line in output.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 4:
            mac = parts[1].lower()
            ip_addr = parts[2]
            hostname = parts[3]
            leases[ip_addr] = hostname
    print(f"[INFO] DHCP leases on {ip}: {len(leases)} entries\n{leases}")
    return leases


# 🧠 Main logic
G = nx.Graph()
mac_to_ap = {}
ip_hostname_map = {}

# 0. Collect DHCP leases
for ap_name, node in mesh_nodes.items():
    leases = get_dhcp_leases(node['ip'], node['user'], node['password'])
    ip_hostname_map.update(leases)
print(f"[INFO] Total DHCP leases: {len(ip_hostname_map)} entries\n{ip_hostname_map}")

# 1. Nodes & clients
for ap_name, node in mesh_nodes.items():
    ip = node['ip']
    user = node['user']
    password = node['password']

    G.add_node(ap_name, type='ap')

    clients = get_clients(ip, user, password)
    for client in clients:
        mac = client['mac'].lower()
        ip_addr = mac_ip_map.get(mac, 'unknown')
        label_parts = [ip_addr, mac]
        label = '\n'.join(p for p in label_parts if p and p != 'unknown')

        G.add_node(label, type='client')
        percent = dbm_to_percent(client['signal'])
        G.add_edge(ap_name, label, signal=percent, type='client')

    mesh_links = get_mesh_links(ip, user, password)
    for link in mesh_links:
        remote_mac = link['remote_mac'].lower()
        percent = dbm_to_percent(link['signal'])
        mac_to_ap.setdefault(remote_mac, []).append((ap_name, percent))

# 2. Resolve hostnames
resolver = list(mesh_nodes.values())[0]
for mac, ip_addr in mac_ip_map.items():
    try:
        cmd = f"getent hosts {ip_addr} | awk '{{print $2}}'"
        hostname = run_ssh_command(resolver['ip'], resolver['user'], resolver['password'], cmd).strip()
        if hostname:
            ip_hostname_map[ip_addr] = hostname
    except:
        pass

# 3. Detect mesh links & optionally measure iperf3
print(f"[INFO] Collecting information for up to {int((len(mesh_nodes) * (len(mesh_nodes)-1))/2)} mesh links...")
tested_pairs = set()  # contains tuples (ap1, ap2), sorted alphabetically
counter = 1
for ap1_name, node1 in mesh_nodes.items():
    ip1 = node1['ip']
    output = run_ssh_command(ip1, node1['user'], node1['password'], "iw dev | grep addr")
    local_macs = [line.split()[-1].lower() for line in output.strip().split('\n') if line]
    for mac in local_macs:
        if mac in mac_to_ap:
            for ap2, signal in mac_to_ap[mac]:
                if ap1_name != ap2:
                    pair = tuple(sorted([ap1_name, ap2]))  # alphabetically sorted
                    if pair in tested_pairs:
                        continue  # already tested
                    tested_pairs.add(pair)

                    throughput, latency = (None, None)
                    if ENABLE_IPERF3_TESTS:
                        throughput, latency = run_iperf3_test(ap1_name, ap2, node1, mesh_nodes[ap2], counter)
                        counter += 1
                    G.add_edge(ap1_name, ap2, signal=signal, type='mesh',
                               throughput=throughput, latency=latency)


# 🎨 Visualization
pos = nx.spring_layout(G, seed=42)
colors, labels, edge_labels, edge_styles = [], {}, {}, []
# Collect router IPs first
ap_ips = {}
for ap_name, node in mesh_nodes.items():
    ip_or_host = node['ip']
    try:
        ip = socket.gethostbyname(ip_or_host)  # Hostname → IP
    except socket.gaierror:
        ip = ip_or_host  # fallback if resolution fails
    ap_ips[ap_name] = ip

for n in G.nodes:
    if G.nodes[n]['type'] == 'ap':
        colors.append('skyblue')
        ip = ap_ips.get(n, 'unknown')
        labels[n] = f"{n}\n{ip}"  # Hostname + IP
    else:
        try:
            ip_addr, mac_addr = n.split('\n')
            hostname = ip_hostname_map.get(ip_addr, '')
            labels[n] = f"{hostname}\n{ip_addr}\n{mac_addr}" if hostname else n
        except:
            labels[n] = n
        colors.append('lightgreen')

for u, v, data in G.edges(data=True):
    parts = []
    if data.get('signal') is not None:
        parts.append(f"{data['signal']}%")
    if data.get('throughput'):
        parts.append(f"{data['throughput']:.2f} Mbit/s")
    if data.get('latency'):
        parts.append(f"{data['latency']:.2f} ms")
    edge_labels[(u, v)] = " / ".join(parts)
    edge_styles.append('dashed' if data['type'] == 'mesh' else 'solid')

plt.figure(figsize=(12, 8))
nx.draw_networkx_nodes(G, pos, node_color=colors, node_size=800)
nx.draw_networkx_labels(G, pos, labels, font_size=8)
for (u, v), style in zip(G.edges(), edge_styles):
    nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], style=style, width=1.5)
nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=7)
title = "Mesh network with clients and link quality"
if ENABLE_IPERF3_TESTS:
    title += " (incl. iperf3 & ping)"
plt.title(title)
plt.axis("off")
plt.tight_layout()
plt.savefig("mesh_network_with_links.pdf", dpi=300)
plt.show()
