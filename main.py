#!/usr/bin/env python3
"""macOS LAN scanner: a 3D star chart of the devices on the local network.

Run with: sudo .venv/bin/python main.py

Root is only used by a small helper that sends the ARP scan. The window itself
is started as the normal user, so no web content ever runs as root.
"""
import concurrent.futures
import csv
import ipaddress
import json
import os
import pwd
import socket
import subprocess
import sys
import threading
from pathlib import Path

import netifaces
from mac_vendor_lookup import MacLookup, VendorNotFoundError

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


def arp_scan(iface, network):
    """Return {ip: mac} for hosts answering ARP. Raises Scapy's permission error without root."""
    # Imported here so the window process, which never scans, starts fast.
    from scapy.all import ARP, Ether, conf, srp

    # Optional: Homebrew's libpcap is used when installed, otherwise Scapy's native BPF.
    if any(Path(prefix, "opt/libpcap").exists() for prefix in ("/opt/homebrew", "/usr/local")):
        conf.use_pcap = True
    answered, _ = srp(
        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=str(network)),
        iface=iface, timeout=2, retry=1, verbose=False,
    )
    return {reply.psrc: reply.hwsrc for _, reply in answered}


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
        mac = ":".join(part.zfill(2) for part in parts[1].split(":"))
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


def serve_scans(requests, replies):
    """Root helper loop: each line is an interface name, each reply one JSON result."""
    for line in requests:
        try:
            result = scan(line.strip() or None)
        except Exception as error:
            result = {"error": str(error)}
        replies.write(json.dumps(result) + "\n")
        replies.flush()


def helper_scanner(requests, replies):
    """Return a function that asks the root helper for a scan over the given pipes."""
    def ask(iface_name):
        requests.write((iface_name or "") + "\n")
        requests.flush()
        reply = replies.readline()
        return json.loads(reply) if reply else {"error": "The scan helper stopped."}
    return ask


def direct_scanner(iface_name):
    try:
        return scan(iface_name)
    except Exception as error:
        return {"error": str(error)}


class Api:
    """Methods the page calls through pywebview. Underscore names stay hidden from it."""

    def __init__(self, scanner, needs_root=False):
        self._scanner = scanner
        self._needs_root = needs_root
        self._names = load_names()
        self._roles = load_map(ROLES_FILE)
        self._rows = []
        self._window = None
        self._lock = threading.Lock()

    def interfaces(self):
        return [{"name": info[0], "ip": info[1]} for info in list_interfaces()]

    def scan(self, iface_name=None):
        with self._lock:
            result = self._scanner(iface_name)
        if "error" in result:
            return {"error": result["error"], "needsRoot": self._needs_root}
        self._rows = result["rows"]
        return {**self._listing(), "network": result["network"], "interface": result["interface"]}

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

    NSBundle.mainBundle().infoDictionary()["CFBundleName"] = "LAN Scanner"
    icon = NSImage.alloc().initWithContentsOfFile_(str(PROJECT / "assets" / "AppIcon.png"))
    NSApplication.sharedApplication().setApplicationIconImage_(icon)


def run_window(scanner, needs_root=False):
    import webview

    set_app_identity()
    api = Api(scanner, needs_root)
    api._window = webview.create_window(
        "LAN Scanner", str(PROJECT / "web" / "index.html"), js_api=api,
        width=1280, height=820, min_size=(960, 620), background_color="#f8fafc",
    )
    webview.start(http_server=True)


def run_as_root():
    """Stay root only for scanning and start the window as the real user."""
    uid = int(os.environ.get("SUDO_UID", Path(__file__).stat().st_uid))
    if uid == 0:
        sys.exit("Start this from your normal account with sudo, not from a root shell.")
    user = pwd.getpwuid(uid)
    env = {key: value for key, value in os.environ.items() if not key.startswith("SUDO_")}
    env.update(HOME=user.pw_dir, USER=user.pw_name, LOGNAME=user.pw_name)

    request_read, request_write = os.pipe()
    reply_read, reply_write = os.pipe()
    window = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--window", str(request_write), str(reply_read)],
        user=uid, group=user.pw_gid, extra_groups=os.getgrouplist(user.pw_name, user.pw_gid), env=env,
        pass_fds=(request_write, reply_read), stdin=subprocess.DEVNULL,
    )
    os.close(request_write)
    os.close(reply_read)
    with os.fdopen(request_read) as requests, os.fdopen(reply_write, "w") as replies:
        serve_scans(requests, replies)
    sys.exit(window.wait())


def main():
    if sys.argv[1:2] == ["--window"]:
        requests = os.fdopen(int(sys.argv[2]), "w")
        replies = os.fdopen(int(sys.argv[3]))
        run_window(helper_scanner(requests, replies))
    elif os.geteuid() == 0:
        run_as_root()
    else:
        # Not a hard stop: ChmodBPF (installed with Wireshark) lets non-root users capture.
        run_window(direct_scanner, needs_root=True)


if __name__ == "__main__":
    main()
