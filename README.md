# Overview
Creates a map of OpenWrt mesh nodes and clients connected via WiFi using paramiko (SSH), matplotlib and networkx, and adds information (signal strength, throughput and latency) to the mesh links. Client links only have signal strength (%). Requires Python v3. Hopefully, this helps in setting up a better mesh topology.

A *mesh node* (blue) is an OpenWrt router configured to be part of a 802.11s mesh. A *mesh link* (dashed line) is a connection between two mesh nodes. A *client* (e.g., your smartphone) is represented as a yellow circle. A *client link* is a connection between a client and a mesh node.

To use this:
- Clone this repo: `git clone git@github.com:CodeFinder2/python-openwrt-mesh-map.git && cd python-openwrt-mesh-map`.
- Create a virtual environment: `python3 -m venv env && source env/bin/activate`.
- Install dependencies: `pip install -r requirements.txt`.
- Add your router setup (hostnames, username, passwords) in `mesh_nodes.py`. To use SSH keys, set an empty password.
- Run `python main.py` and wait for the resulting diagram. You must be connected to one of the routers.

This has been tested with [OpenWrt 24.10.4](https://openwrt.org/releases/24.10/changelog-24.10.4) on four [Linksys MX5300](https://openwrt.org/toh/linksys/mx5300) devices forming a [pure 802.11s mesh](https://www.onemarcfifty.com/blog/video/wifi-mesh-diy/):

![example](https://github.com/user-attachments/assets/2088ef5c-2472-4743-86da-eb98ae243fed)

# Notes
- It has been observed that a client has been displayed with more than one connection, i.e., there were multiple client links (lines from one client to more than one mesh node). This seems to be related to the update interval of the kernel (network driver stack). That is, in such cases, the client was also listed in the OpenWrt Status page of the respective mesh nodes. After some time, it should disappear.
