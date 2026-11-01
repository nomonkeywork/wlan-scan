"""Run with: .venv/bin/python -m unittest -v  (no root or real network scan needed)"""
import csv
import io
import json
import os
import tempfile
import unittest
from unittest import mock

import netifaces

import main

GW_MAC = "00:00:5e:00:53:01"
SHARED_MAC = "00:00:5e:00:53:02"
ROWS = [
    ["192.168.1.1", GW_MAC, "TIBRO Corp.", "Router/Gateway", "", True, "", ""],
    ["192.168.1.97", SHARED_MAC, "Private (randomized MAC)", "Device", "", True, "", ""],
    ["192.168.1.98", SHARED_MAC, "Private (randomized MAC)", "Device", "MacBook-Pro-2", False, "fe80::1", "fd00::1, fd00::2"],
]


def fake_addrs(ipv4):
    return {netifaces.AF_INET: [ipv4], netifaces.AF_LINK: [{"addr": "aa:bb:cc:dd:ee:ff"}]}


class FindInterface(unittest.TestCase):
    def run_with(self, routes, interfaces):
        with mock.patch("netifaces.gateways", return_value={netifaces.AF_INET: routes}), \
                mock.patch("netifaces.interfaces", return_value=list(interfaces)), \
                mock.patch("netifaces.ifaddresses", side_effect=lambda name: interfaces[name]):
            return main.find_interface()

    def test_skips_vpn_default_route(self):
        interfaces = {
            "utun3": fake_addrs({"addr": "10.8.0.2", "netmask": "255.255.255.255", "peer": "10.8.0.1"}),
            "en5": fake_addrs({"addr": "192.168.1.5", "netmask": "255.255.255.0", "broadcast": "192.168.1.255"}),
        }
        routes = [("10.8.0.1", "utun3", True), ("192.168.1.1", "en5", False)]
        result = self.run_with(routes, interfaces)
        self.assertEqual((result[0], result[4]), ("en5", "192.168.1.1"))

    def test_falls_back_to_interfaces_without_route(self):
        interfaces = {"en0": fake_addrs({"addr": "192.168.1.5", "netmask": "255.255.255.0", "broadcast": "192.168.1.255"})}
        self.assertEqual(self.run_with([], interfaces)[4], None)

    def test_picks_named_interface_or_falls_back_to_best(self):
        en0 = ("en0", "192.168.1.5", "255.255.255.0", "aa", "192.168.1.1")
        en5 = ("en5", "10.0.0.5", "255.255.255.0", "bb", None)
        with mock.patch("main.list_interfaces", return_value=[en0, en5]):
            self.assertEqual(main.find_interface("en5"), en5)
            self.assertEqual(main.find_interface("gone"), en0)
            self.assertEqual(main.find_interface(), en0)

    def test_ignores_link_local_and_raises_when_nothing_usable(self):
        interfaces = {"en0": fake_addrs({"addr": "169.254.1.2", "netmask": "255.255.0.0", "broadcast": "169.254.255.255"})}
        with self.assertRaises(RuntimeError):
            self.run_with([], interfaces)


class Logic(unittest.TestCase):
    def test_scan_range_caps_large_networks(self):
        self.assertEqual(str(main.scan_range("10.0.5.9", "255.255.0.0")), "10.0.5.0/24")
        self.assertEqual(str(main.scan_range("192.168.1.9", "255.255.255.128")), "192.168.1.0/25")

    def test_vendor_name(self):
        lookup = mock.Mock(lookup=mock.Mock(side_effect=main.VendorNotFoundError("x")))
        self.assertEqual(main.vendor_name(lookup, "3a:00:00:00:00:01"), "Private (randomized MAC)")
        self.assertEqual(main.vendor_name(lookup, "38:00:00:00:00:01"), "Unknown")
        self.assertEqual(main.vendor_name(None, "38:00:00:00:00:01"), "Unknown (no OUI database)")

    def test_classify(self):
        def role(ip, mac, vendor, port_open=True):
            return main.classify(ip, mac, vendor, "192.168.1.5", "192.168.1.1", GW_MAC, lambda _: port_open)

        self.assertEqual(role("192.168.1.1", GW_MAC, "AVM"), "Router/Gateway")
        self.assertEqual(role("192.168.1.5", "00:11:22:33:44:55", "Apple, Inc."), "This Mac")
        self.assertEqual(role("192.168.1.9", "00:11:22:33:44:55", "Ubiquiti Inc"), "Suspected AP")
        self.assertEqual(role("192.168.1.9", "00:00:5e:00:00:01", "Unknown"), "Suspected AP")
        self.assertEqual(role("192.168.1.9", "00:11:22:33:44:55", "TP-LINK", port_open=False), "Device")
        self.assertEqual(role("192.168.1.9", "00:11:22:33:44:55", "Apple, Inc."), "Device")

    def test_scan_adds_this_mac_sorted_by_ip(self):
        info = ("en0", "192.168.1.5", "255.255.255.0", "38:bb:cc:dd:ee:ff", "192.168.1.1")
        hosts = {"192.168.1.20": "38:00:00:00:00:20", "192.168.1.1": GW_MAC}
        with mock.patch("main.find_interface", return_value=info) as find, \
                mock.patch("main.arp_scan", return_value=hosts), \
                mock.patch("main.load_vendor_lookup", return_value=None), \
                mock.patch("main.enrich", side_effect=lambda rows: rows):
            result = main.scan("en0")
        find.assert_called_once_with("en0")
        self.assertEqual(result["network"], "192.168.1.0/24")
        self.assertEqual([(r[0], r[3]) for r in result["rows"]], [
            ("192.168.1.1", "Router/Gateway"), ("192.168.1.5", "This Mac"), ("192.168.1.20", "Device"),
        ])

    def test_group_devices_merges_ips_of_one_mac(self):
        rows = ROWS + [["192.168.1.99", SHARED_MAC, "Private (randomized MAC)", "Suspected AP", "", None, "", ""]]
        groups = main.group_devices(rows, {SHARED_MAC: "Extender"})
        self.assertEqual([g["mac"] for g in groups], [GW_MAC, SHARED_MAC])
        self.assertEqual(groups[1]["ips"], ["192.168.1.97", "192.168.1.98", "192.168.1.99"])
        self.assertEqual((groups[1]["name"], groups[1]["role"]), ("Extender", "Suspected AP"))
        self.assertEqual(groups[1]["hostnames"], ["MacBook-Pro-2"])
        self.assertEqual(groups[1]["ipv6"], ["fe80::1", "fd00::1", "fd00::2"])

    def test_ipv6_neighbors_parses_ndp_and_pads_mac(self):
        output = """Neighbor  Linklayer Address  Netif Expire St Flgs Prbs
fe80::1%lo0  (incomplete)  lo0 permanent R
fe80::db8:1%en0  00:00:5e:00:53:02  en0 23h S
fd00:db8::1  0:0:5e:0:53:f  en0 23h S
"""
        with mock.patch("subprocess.run", return_value=mock.Mock(stdout=output)):
            self.assertEqual(main.ipv6_neighbors(), {
                SHARED_MAC: (["fe80::db8:1"], []),
                "00:00:5e:00:53:0f": ([], ["fd00:db8::1"]),
            })

    def test_mdns_hostname_strips_local_and_ignores_errors(self):
        with mock.patch("subprocess.run", return_value=mock.Mock(stdout="MacBook-Pro-2.local.\n")):
            self.assertEqual(main.mdns_hostname("192.168.1.98"), "MacBook-Pro-2")
        with mock.patch("subprocess.run", return_value=mock.Mock(stdout=";; connection timed out\n")):
            self.assertEqual(main.mdns_hostname("192.168.1.97"), "")

    def test_enrich_puts_ipv6_on_the_named_row_of_a_shared_mac(self):
        rows = [row[:4] for row in ROWS]
        with mock.patch("main.responds_to_ping", side_effect=lambda ip: ip != "192.168.1.97"), \
                mock.patch("main.mdns_hostname", side_effect=lambda ip: "Book" if ip == "192.168.1.98" else ""), \
                mock.patch("main.ipv6_neighbors", return_value={SHARED_MAC: (["fe80::1"], ["fd00::1"])}):
            enriched = main.enrich(rows)
        self.assertEqual(enriched[0][4:], ["", True, "", ""])
        self.assertEqual(enriched[1][4:], ["", False, "", ""])
        self.assertEqual(enriched[2][4:], ["Book", True, "fe80::1", "fd00::1"])


class ScanHelper(unittest.TestCase):
    def test_helper_answers_each_request_and_reports_errors(self):
        results = [{"rows": [], "network": "n", "interface": "en0"}, RuntimeError("no network")]
        replies = io.StringIO()
        with mock.patch("main.scan", side_effect=results) as scan:
            main.serve_scans(io.StringIO("en5\n\n"), replies)
        self.assertEqual(scan.call_args_list, [mock.call("en5"), mock.call(None)])
        lines = replies.getvalue().splitlines()
        self.assertEqual(json.loads(lines[0])["interface"], "en0")
        self.assertEqual(json.loads(lines[1]), {"error": "no network"})

    def test_window_side_asks_helper_and_survives_it_stopping(self):
        requests = io.StringIO()
        ask = main.helper_scanner(requests, io.StringIO('{"rows": []}\n'))
        self.assertEqual(ask("en5"), {"rows": []})
        self.assertEqual(requests.getvalue(), "en5\n")
        self.assertIn("error", ask("en5"))


class Names(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = main.Path(folder.name, "names.json")
        for name, path in (("NAMES_FILE", self.path), ("ROLES_FILE", self.path.with_name("roles.json"))):
            patcher = mock.patch(f"main.{name}", path)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_save_and_load_round_trip(self):
        self.assertEqual(main.load_names(), {})
        main.save_names({GW_MAC: "Küchen-Router"})
        self.assertEqual(main.load_names(), {GW_MAC: "Küchen-Router"})
        self.assertEqual([p.name for p in self.path.parent.iterdir()], ["names.json"])

    def test_broken_file_is_kept_not_overwritten(self):
        self.path.write_text("{oops")
        self.assertEqual(main.load_names(), {})
        self.assertEqual(self.path.with_suffix(".json.bad").read_text(), "{oops")

    def scanned_api(self):
        api = main.Api(lambda _: {"rows": ROWS, "network": "192.168.1.0/24", "interface": "en0"})
        api.scan("en0")
        return api

    def test_rename_is_stored_by_mac_and_survives_restart(self):
        api = self.scanned_api()
        result = api.rename(SHARED_MAC.upper(), "  007 TV ")
        self.assertEqual(result["devices"][1]["name"], "007 TV")
        self.assertEqual(self.scanned_api().scan("en0")["devices"][1]["name"], "007 TV")

    def test_empty_name_clears_it(self):
        api = self.scanned_api()
        api.rename(GW_MAC, "Router")
        api.rename(GW_MAC, "   ")
        self.assertEqual(main.load_names(), {})

    def test_failed_save_keeps_old_name_and_reports(self):
        api = self.scanned_api()
        with mock.patch("main.save_names", side_effect=OSError("disk full")):
            self.assertEqual(api.rename(GW_MAC, "Router"), {"error": "disk full"})
        self.assertEqual(api.scan("en0")["devices"][0]["name"], "")

    def test_role_override_is_stored_by_mac_and_survives_restart(self):
        api = self.scanned_api()
        listing = api.set_role(SHARED_MAC.upper(), "Access point")
        device = listing["devices"][1]
        self.assertEqual((device["role"], device["detectedRole"], device["roleOverride"]), ("Access point", "Device", "Access point"))
        self.assertEqual({row["role"] for row in listing["table"] if row["mac"] == SHARED_MAC}, {"Access point"})
        self.assertEqual(self.scanned_api().scan("en0")["devices"][1]["role"], "Access point")

    def test_automatic_clears_the_override(self):
        api = self.scanned_api()
        api.set_role(SHARED_MAC, "Access point")
        self.assertEqual(api.set_role(SHARED_MAC, "")["devices"][1]["role"], "Device")
        self.assertEqual(main.load_map(main.ROLES_FILE), {})

    def test_unknown_role_is_refused(self):
        self.assertIn("error", self.scanned_api().set_role(GW_MAC, "Router/Gateway"))

    def test_gateway_role_cannot_be_overridden(self):
        main.save_map(main.ROLES_FILE, {GW_MAC: "Device"})
        device = self.scanned_api().scan("en0")["devices"][0]
        self.assertEqual((device["role"], device["roleFixed"]), ("Router/Gateway", True))

    def test_open_in_browser_only_opens_scanned_addresses(self):
        api = self.scanned_api()
        with mock.patch("webbrowser.open", return_value=True) as browser:
            self.assertEqual(api.open_in_browser("192.168.1.97"), {})
            self.assertIn("error", api.open_in_browser("https://evil.example"))
        browser.assert_called_once_with("http://192.168.1.97/")

    def test_scan_error_reports_whether_root_is_the_fix(self):
        api = main.Api(lambda _: {"error": "denied"}, needs_root=True)
        self.assertEqual(api.scan("en0"), {"error": "denied", "needsRoot": True})


class Export(unittest.TestCase):
    def test_write_csv_round_trip_with_names(self):
        rows = [["192.168.1.1", GW_MAC, 'Acme, "Inc."', "Router/Gateway", "gw", False, "fe80::1", ""]]
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "scan.csv")
            main.write_csv(path, rows, {GW_MAC: "007"})
            with open(path, newline="", encoding="utf-8") as file:
                self.assertEqual(list(csv.reader(file)), [
                    ["Name", "IP", "MAC", "Vendor", "Role", "Hostname", "Ping", "IPv6 local", "IPv6 global"],
                    ["007", "192.168.1.1", GW_MAC, 'Acme, "Inc."', "Router/Gateway", "gw", "down", "fe80::1", ""],
                ])


if __name__ == "__main__":
    unittest.main()
