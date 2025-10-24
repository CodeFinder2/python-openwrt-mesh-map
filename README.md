# Overview
Creates a map of a all OpenWrt mesh nodes and clients connected via WiFi using paramiko (SSH), matplotlib and networkx, and adds information (signal strength, throughput and latency) to the mesh links. Client links only have signal strength (%). Requires Python v3.

To use this:
- Clone this repo: `git clone git@github.com:CodeFinder2/python-openwrt-mesh-map.git && cd python-openwrt-mesh-map`.
- Create a virtual environment: `python3 -v venv env && source env/bin/activate`.
- Install dependencies: `pip install -r requirements.txt`.
- Add your router setup (hostnames, username, passwords) in `mesh_nodes.py`.
- Run `python main.py` and wait for the resulting diagram. You must be connected to one of the routers.

This has been tested with [OpenWrt 24.10.4](https://openwrt.org/releases/24.10/changelog-24.10.4) on four [Linksys MX5300](https://openwrt.org/toh/linksys/mx5300) devices forming a [pure 802.11s mesh](https://www.onemarcfifty.com/blog/video/wifi-mesh-diy/).

![example](https://github.com/user-attachments/assets/2088ef5c-2472-4743-86da-eb98ae243fed)
