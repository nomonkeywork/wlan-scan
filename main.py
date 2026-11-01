#!/usr/bin/env python3
"""macOS LAN scanner: a 3D star chart of the devices on the local network.

Run with: .venv/bin/python main.py

No root needed: sending to each address makes macOS do the ARP, and anyone can
read the result from its ARP table.
"""
import concurrent.futures
import csv
import ipaddress
import json
import os
import pty
import re
import select
import socket
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import netifaces
from mac_vendor_lookup import MacLookup, VendorNotFoundError

APP_NAME = "Freds LAN"
PROJECT = Path(__file__).resolve().parent
NAMES_FILE = PROJECT / "names.json"
ROLES_FILE = PROJECT / "roles.json"
CHOOSABLE_ROLES = ("Access point", "Device")
# Measured, not guessed, so these can't be overridden.
FIXED_ROLES = ("Router/Gateway", "This Mac")
# Lowercase substrings of IEEE vendor names that commonly make access points.
AP_VENDORS = (
    "ubiquiti", "tp-link", "netgear", "aruba", "ruckus", "cisco", "mikrotik",
    "engenius", "linksys", "asustek", "d-link", "zyxel", "eero", "cambium",
    "grandstream", "tenda", "avm audiovisuelles",
)
MANAGEMENT_PORTS = (22, 80, 443)
DISCARD_PORT = 9
SPEED_SILENCE_TIMEOUT = 30
SPEED_MAX_SECONDS = "60"
PING_SAMPLES = 8
WIFI_BANDS = {1: "2.4 GHz", 2: "5 GHz", 3: "6 GHz"}  # CoreWLAN's CWChannelBand values.
WIFI_SECURITY_NONE = 0  # CoreWLAN's kCWSecurityNone.
IP_BOUND_IF = 25  # macOS's socket option for sending through one interface. Python has no name for it.
LOCAL_NETWORK_HELP = (
    "macOS blocked access to the network. In System Settings, open Privacy & Security, then Local Network, "
    f"turn on {APP_NAME}, and scan again."
)
CSV_HEADER = ("Name", "IP", "MAC", "Vendor", "Role", "Hostname", "Ping", "IPv6 local", "IPv6 global")
PING_TEXT = {True: "up", False: "down", None: ""}


def list_interfaces():
    """Return (iface, ip, netmask, mac, gateway_ip) per scannable interface, best first."""
    found = {}
    routes = netifaces.gateways().get(netifaces.AF_INET, [])
    candidates = [(gw, iface) for gw, iface, _ in sorted(routes, key=lambda r: not r[2])]
    # A full-tunnel VPN can hide the LAN route, so also try interfaces directly, en* first.
    candidates += [(None, n) for n in sorted(netifaces.interfaces(), key=lambda n: not n.startswith("en"))]
    for gateway, iface in candidates:
        addrs = netifaces.ifaddresses(iface)
        ipv4 = addrs.get(netifaces.AF_INET, [{}])[0]
        # No broadcast means a point-to-point link such as a VPN's utun, where ARP cannot work.
        if iface not in found and "broadcast" in ipv4 and not ipaddress.ip_address(ipv4["addr"]).is_link_local:
            found[iface] = (iface, ipv4["addr"], ipv4["netmask"], addrs[netifaces.AF_LINK][0]["addr"], gateway)
    return list(found.values())


def find_interface(name=None):
    """Return the interface called `name`, or the best one if it is gone or not given."""
    found = list_interfaces()
    if not found:
        raise RuntimeError("No active network interface found. Check Wi-Fi or Ethernet.")
    return next((info for info in found if info[0] == name), found[0])


def scan_range(ip, netmask):
    network = ipaddress.ip_interface(f"{ip}/{netmask}").network
    # shortcut: networks larger than /24 only scan the local /24, add batching if whole /16s matter.
    return network if network.prefixlen >= 24 else ipaddress.ip_network(f"{ip}/24", strict=False)


def full_mac(mac):
    """macOS tools drop leading zeros (0:7d:3b...), but names are stored by the full form."""
    return ":".join(part.zfill(2) for part in mac.split(":"))


def arp_table(iface):
    output = subprocess.run(["arp", "-an", "-i", iface], capture_output=True, text=True).stdout
    return {ip: full_mac(mac) for ip, mac in re.findall(r"\((\S+)\) at ([0-9a-f:]+) on", output)}


def arp_scan(iface, network):
    """Return {ip: mac} for hosts answering ARP, which macOS asks when something is sent to them."""
    hosts = [str(host) for host in network.hosts()]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setblocking(False)
        sock.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF, socket.if_nametoindex(iface))
        for _ in range(2):  # A second round catches devices that missed the first.
            sent = 0
            for host in hosts:
                try:
                    sock.sendto(b"", (host, DISCARD_PORT))
                    sent += 1
                except OSError:
                    pass
            if not sent:
                raise RuntimeError(LOCAL_NETWORK_HELP)
            time.sleep(1.5)
    return {ip: mac for ip, mac in arp_table(iface).items() if ip in hosts}


def load_vendor_lookup():
    """Return a MacLookup using the OUI list bundled with the package, or None if unavailable."""
    lookup = MacLookup()
    try:
        lookup.load_vendors()
    except Exception:  # A missing list triggers a download; a scan is still useful without vendors.
        return None
    return lookup


def vendor_name(lookup, mac):
    # This bit marks a locally administered address, which phones use for Wi-Fi privacy.
    if int(mac[1], 16) & 2:
        return "Private (randomized MAC)"
    if lookup is None:
        return "Unknown (no OUI database)"
    try:
        return lookup.lookup(mac)
    except VendorNotFoundError:
        return "Unknown"


def has_management_port(ip):
    for port in MANAGEMENT_PORTS:
        try:
            socket.create_connection((ip, port), timeout=0.5).close()
            return True
        except OSError:
            pass
    return False


def classify(ip, mac, vendor, own_ip, gateway_ip, gateway_mac, probe=has_management_port):
    if ip == gateway_ip:
        return "Router/Gateway"
    if ip == own_ip:
        return "This Mac"
    same_brand_as_router = gateway_mac and mac[:8].lower() == gateway_mac[:8].lower()
    # The port check filters out smart plugs and phones from the same vendors.
    if (same_brand_as_router or any(k in vendor.lower() for k in AP_VENDORS)) and probe(ip):
        return "Suspected AP"
    return "Device"


def responds_to_ping(ip):
    return subprocess.run(["ping", "-c", "1", "-t", "1", ip], capture_output=True).returncode == 0


def mdns_hostname(ip):
    """Ask over multicast DNS, which is how Macs and many home devices publish their names."""
    result = subprocess.run(
        ["dig", "-x", ip, "@224.0.0.251", "-p", "5353", "+short", "+time=1", "+tries=1"],
        capture_output=True, text=True,
    )
    names = [line for line in result.stdout.splitlines() if line.endswith(".")]
    return names[0].removesuffix(".").removesuffix(".local") if names else ""


def ipv6_neighbors():
    """Return {mac: ([local addresses], [global addresses])} from the system's neighbour table."""
    try:
        output = subprocess.run(["ndp", "-an"], capture_output=True, text=True).stdout
    except OSError:
        return {}
    neighbors = {}
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or ":" not in parts[1]:
            continue
        address = parts[0].split("%")[0]
        mac = full_mac(parts[1])
        local, global_ = neighbors.setdefault(mac, ([], []))
        (local if address.startswith("fe80:") else global_).append(address)
    return neighbors


def enrich(rows):
    """Append hostname, ping, IPv6 local and IPv6 global to each [ip, mac, vendor, role] row."""
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=32)
    pings = [executor.submit(responds_to_ping, row[0]) for row in rows]
    names = [executor.submit(mdns_hostname, row[0]) for row in rows]
    # A device that never answers must not hold up the whole scan.
    concurrent.futures.wait(pings + names, timeout=3)
    executor.shutdown(wait=False, cancel_futures=True)

    def result(future, fallback):
        return future.result() if future.done() and not future.cancelled() and not future.exception() else fallback

    neighbors = ipv6_neighbors()
    enriched = [[*row, result(name, ""), result(ping, None), "", ""] for row, name, ping in zip(rows, names, pings)]
    # An extender answers for its clients with one MAC, so IPv6 goes on one row of that MAC: the named one if any.
    for mac, (local, global_) in neighbors.items():
        same_mac = [row for row in enriched if row[1].lower() == mac]
        if same_mac:
            owner = next((row for row in same_mac if row[4]), same_mac[0])
            owner[6], owner[7] = ", ".join(local), ", ".join(global_)
    return enriched


def scan(iface_name=None):
    """Run a full scan and return {"rows": [[ip, mac, vendor, role, hostname, ping, ipv6 local, ipv6 global]], ...}."""
    iface, ip, netmask, mac, gateway = find_interface(iface_name)
    network = scan_range(ip, netmask)
    hosts = arp_scan(iface, network)
    hosts[ip] = mac  # A host never answers its own ARP request.

    lookup = load_vendor_lookup()
    rows = []
    for host, host_mac in sorted(hosts.items(), key=lambda item: ipaddress.ip_address(item[0])):
        vendor = vendor_name(lookup, host_mac)
        rows.append([host, host_mac, vendor, classify(host, host_mac, vendor, ip, gateway, hosts.get(gateway))])
    return {"rows": enrich(rows), "network": str(network), "interface": iface}


def read_capacity(command, label, report):
    """Run networkQuality in a terminal, the only place it prints live speeds, and return its final figure."""
    master, slave = pty.openpty()
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=slave, stderr=slave)
    os.close(slave)
    recent = ""
    capacity = None
    last_output = time.monotonic()
    try:
        while time.monotonic() - last_output < SPEED_SILENCE_TIMEOUT:
            if not select.select([master], [], [], 1)[0]:
                if process.poll() is not None:
                    break
                continue
            try:
                chunk = os.read(master, 4096)
            except OSError:  # The terminal closes when the tool exits.
                break
            if not chunk:
                break
            last_output = time.monotonic()
            # A number can be split across two reads, so keep the end of the previous one.
            recent = recent[-200:] + chunk.decode(errors="ignore")
            live = re.findall(rf"{label}: ([\d.]+) Mbps", recent)
            if live:
                report(float(live[-1]))
            final = re.search(rf"{label} capacity: ([\d.]+) Mbps", recent)
            if final:
                capacity = float(final[1])
    finally:
        process.kill()
        process.wait()
        os.close(master)
    if capacity is None:
        raise RuntimeError("networkQuality gave no result")
    return capacity


def download_test(iface, report):
    return read_capacity(["networkQuality", "-u", "-M", SPEED_MAX_SECONDS, "-I", iface], "Downlink", report)


def upload_test(iface, report):
    return read_capacity(["networkQuality", "-d", "-M", SPEED_MAX_SECONDS, "-I", iface], "Uplink", report)


def ping_test(iface, report):
    """Sample idle latency without loading the connection. The median ignores one slow reply."""
    samples = []
    for _ in range(PING_SAMPLES):
        output = subprocess.run(
            ["networkQuality", "-u", "-d", "-c", "-I", iface], capture_output=True, text=True, timeout=15,
        ).stdout
        samples.append(json.loads(output)["base_rtt"])
        report(samples[-1])
    return statistics.median(samples)


def known_wifi(iface):
    """Return the Wi-Fi names this Mac has saved. macOS shows these without Location permission."""
    output = subprocess.run(
        ["networksetup", "-listpreferredwirelessnetworks", iface], capture_output=True, text=True,
    ).stdout
    return {line.strip() for line in output.splitlines()[1:]}


def wifi_row(network, known, current):
    name = network.ssid() or ""
    channel = network.wlanChannel()
    return {
        "ssid": name, "signal": network.rssiValue(), "channel": channel.channelNumber(),
        "band": WIFI_BANDS.get(channel.channelBand(), ""),
        "secure": not network.supportsSecurity_(WIFI_SECURITY_NONE),
        "known": name in known, "current": bool(name) and name == current,
    }


def wifi_networks():
    """Return the Wi-Fi networks in range, strongest first."""
    from CoreWLAN import CWWiFiClient

    wifi = CWWiFiClient.sharedWiFiClient().interface()
    if wifi is None:
        raise RuntimeError("This Mac has no Wi-Fi interface.")
    found, error = wifi.scanForNetworksWithName_error_(None, None)
    if error:
        raise RuntimeError(error.localizedDescription())
    known = known_wifi(wifi.interfaceName())
    rows = [wifi_row(network, known, wifi.ssid()) for network in found]
    return sorted(rows, key=lambda row: -row["signal"])


SPEED_TESTS = {"download": download_test, "upload": upload_test, "ping": ping_test}


def group_devices(rows, names):
    """Merge rows by MAC: one physical device can answer on several IPs."""
    devices = {}
    for ip, mac, vendor, role, hostname, _, local, global_ in rows:
        device = devices.setdefault(mac.lower(), {
            "mac": mac.lower(), "name": names.get(mac.lower(), ""), "vendor": vendor, "role": role,
            "ips": [], "hostnames": [], "ipv6": [],
        })
        device["ips"].append(ip)
        if hostname:
            device["hostnames"].append(hostname)
        device["ipv6"] += [address for address in (*local.split(", "), *global_.split(", ")) if address]
        if device["role"] == "Device":
            device["role"] = role
    return list(devices.values())


def write_csv(path, rows, names):
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_HEADER)
        writer.writerows([names.get(row[1].lower(), ""), *row[:5], PING_TEXT[row[5]], *row[6:]] for row in rows)


def load_map(path):
    """Return a saved {mac: value} map."""
    try:
        values = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            raise ValueError("expected a JSON object")
        return values
    except FileNotFoundError:
        return {}
    except ValueError:
        # Keep a broken file instead of overwriting it on the next save.
        os.replace(path, path.with_suffix(".json.bad"))
        return {}


def save_map(path, values):
    # Write then swap, so a crash mid-write can't lose what was saved before.
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(values, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(temp, path)


def load_names():
    return load_map(NAMES_FILE)


def save_names(names):
    save_map(NAMES_FILE, names)


def scanner(iface_name):
    try:
        return scan(iface_name)
    except Exception as error:
        return {"error": str(error)}


class Api:
    """Methods the page calls through pywebview. Underscore names stay hidden from it."""

    def __init__(self, scan_network):
        self._scan_network = scan_network
        self._location = None
        self._speed_live = None
        self._names = load_names()
        self._roles = load_map(ROLES_FILE)
        self._rows = []
        self._window = None
        self._lock = threading.Lock()

    def interfaces(self):
        return [{"name": info[0], "ip": info[1]} for info in list_interfaces()]

    def scan(self, iface_name=None):
        with self._lock:
            result = self._scan_network(iface_name)
        if "error" in result:
            return {"error": result["error"]}
        self._rows = result["rows"]
        return {**self._listing(), "network": result["network"], "interface": result["interface"]}

    def speed_test(self, test, iface_name=None):
        if test not in SPEED_TESTS:
            return {"error": f"Unknown test: {test}"}
        self._speed_live = {"count": 0, "value": 0}

        def report(value):
            self._speed_live = {"count": self._speed_live["count"] + 1, "value": value}

        try:
            iface = find_interface(iface_name)[0]
            return {"value": SPEED_TESTS[test](iface, report), "interface": iface}
        except (OSError, RuntimeError, ValueError, KeyError, subprocess.TimeoutExpired):
            return {"error": "The speed test couldn't finish. Check your internet connection and try again."}

    def speed_live(self):
        return self._speed_live

    def _ask_for_location(self):
        from CoreLocation import CLLocationManager

        # Kept on self because macOS drops the question when the manager is released.
        self._location = CLLocationManager.alloc().init()
        self._location.requestWhenInUseAuthorization()

    def wifi(self):
        from PyObjCTools import AppHelper

        if self._location is None:
            AppHelper.callAfter(self._ask_for_location)
        try:
            networks = wifi_networks()
        except (OSError, RuntimeError) as error:
            return {"error": str(error)}
        return {"networks": networks, "namesHidden": any(not network["ssid"] for network in networks)}

    def _rows_with_roles(self):
        return [
            [*row[:3], self._roles[row[1].lower()], *row[4:]]
            if row[1].lower() in self._roles and row[3] not in FIXED_ROLES else row
            for row in self._rows
        ]

    def _listing(self):
        rows = self._rows_with_roles()
        devices = group_devices(rows, self._names)
        detected = {device["mac"]: device["role"] for device in group_devices(self._rows, {})}
        for device in devices:
            device["detectedRole"] = detected[device["mac"]]
            device["roleOverride"] = self._roles.get(device["mac"], "")
            device["roleFixed"] = detected[device["mac"]] in FIXED_ROLES
        return {
            "devices": devices,
            "table": [
                dict(zip(("ip", "mac", "vendor", "role", "hostname", "ping", "ipv6Local", "ipv6Global"), row),
                     name=self._names.get(row[1].lower(), ""))
                for row in rows
            ],
        }

    def rename(self, mac, name):
        names = dict(self._names)
        names[mac.lower()] = name.strip()
        if not names[mac.lower()]:
            del names[mac.lower()]
        try:
            save_names(names)
        except OSError as error:
            return {"error": str(error)}
        self._names = names
        return self._listing()

    def set_role(self, mac, role):
        """Save a role by MAC. An empty role goes back to automatic detection."""
        if role and role not in CHOOSABLE_ROLES:
            return {"error": f"Unknown role: {role}"}
        roles = dict(self._roles)
        roles[mac.lower()] = role
        if not role:
            del roles[mac.lower()]
        try:
            save_map(ROLES_FILE, roles)
        except OSError as error:
            return {"error": str(error)}
        self._roles = roles
        return self._listing()

    def open_in_browser(self, ip):
        # The page can only open what the scan found, never an arbitrary address.
        if not any(row[0] == ip for row in self._rows):
            return {"error": f"{ip} isn't in the current scan."}
        import webbrowser

        return {} if webbrowser.open(f"http://{ip}/") else {"error": "No browser could be opened."}

    def export(self):
        import webview

        paths = self._window.create_file_dialog(webview.SAVE_DIALOG, save_filename="lan-scan.csv", directory=str(PROJECT))
        if not paths:
            return {}
        path = paths if isinstance(paths, str) else paths[0]
        try:
            write_csv(path, self._rows_with_roles(), self._names)
        except OSError as error:
            return {"error": str(error)}
        return {"saved": path}


def set_app_identity():
    """Show the app's own name and icon in the Dock and menu bar instead of Python's."""
    from AppKit import NSApplication, NSImage
    from Foundation import NSBundle

    NSBundle.mainBundle().infoDictionary()["CFBundleName"] = APP_NAME
    icon = NSImage.alloc().initWithContentsOfFile_(str(PROJECT / "assets" / "AppIcon.png"))
    NSApplication.sharedApplication().setApplicationIconImage_(icon)


def run_window():
    import webview

    set_app_identity()
    api = Api(scanner)
    api._window = webview.create_window(
        APP_NAME, str(PROJECT / "web" / "index.html"), js_api=api,
        width=1280, height=820, min_size=(960, 620), background_color="#f8fafc",
    )
    webview.start(http_server=True)


def main():
    # The window shows web content, which must never run as root.
    if os.geteuid() == 0:
        sys.exit("Start this without sudo. It no longer needs root.")
    run_window()


if __name__ == "__main__":
    main()
