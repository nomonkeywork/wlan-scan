"""Run with: .venv/bin/python -m unittest -v  (no real network scan needed)"""
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


class ArpScan(unittest.TestCase):
    ARP_OUTPUT = """? (192.168.1.1) at 0:0:5e:0:53:1 on en0 ifscope [ethernet]
? (192.168.1.7) at (incomplete) on en0 ifscope [ethernet]
? (192.168.1.255) at ff:ff:ff:ff:ff:ff on en0 ifscope [ethernet]
? (224.0.0.251) at 1:0:5e:0:0:fb on en0 ifscope permanent [ethernet]
"""
    NETWORK = main.ipaddress.ip_network("192.168.1.0/24")

    def run_scan(self, send_error=None):
        with mock.patch("socket.socket") as sock, mock.patch("socket.if_nametoindex", return_value=4), \
                mock.patch("time.sleep"), mock.patch("subprocess.run", return_value=mock.Mock(stdout=self.ARP_OUTPUT)):
            sock.return_value.__enter__.return_value.sendto.side_effect = send_error
            return main.arp_scan("en0", self.NETWORK)

    def test_keeps_answering_hosts_with_full_macs(self):
        self.assertEqual(self.run_scan(), {"192.168.1.1": "00:00:5e:00:53:01"})

    def test_all_sends_failing_points_to_the_local_network_setting(self):
        with self.assertRaisesRegex(RuntimeError, "Local Network"):
            self.run_scan(send_error=OSError("No route to host"))


class SpeedTest(unittest.TestCase):
    def test_reports_live_speeds_and_returns_the_final_figure(self):
        script = (
            r"printf '\r\033[2K\rDownlink: 12.5 Mbps, 0 RPM - Uplink: 0.000 Mbps, 0 RPM'; "
            r"printf '\r\033[2K\rDownlink: 40.0 Mbps, 9 RPM - Uplink: 0.000 Mbps, 0 RPM'; "
            r"printf '\r\033[2K==== SUMMARY ====\r\nDownlink capacity: 38.2 Mbps\r\n'"
        )
        seen = []
        self.assertEqual(main.read_capacity(["sh", "-c", script], "Downlink", seen.append), 38.2)
        self.assertIn(40.0, seen)
        self.assertEqual(seen[-1], 40.0)

    def test_no_final_figure_is_an_error(self):
        with self.assertRaises(RuntimeError):
            main.read_capacity(["sh", "-c", "echo offline"], "Downlink", lambda _: None)

    def test_ping_reports_each_sample_and_returns_the_median(self):
        outputs = iter(['{"base_rtt": %d}' % value for value in (50, 500, 60, 55, 52, 58, 57, 53)])
        seen = []
        with mock.patch("subprocess.run", side_effect=lambda *_, **__: mock.Mock(stdout=next(outputs))):
            self.assertEqual(main.ping_test("en5", seen.append), 56)
        self.assertEqual(len(seen), main.PING_SAMPLES)

    def test_page_can_only_start_known_tests_and_failures_become_messages(self):
        api = main.Api(lambda _: {})
        self.assertIn("error", api.speed_test("reboot"))
        with mock.patch("main.find_interface", return_value=("en0",)), \
                mock.patch("subprocess.run", return_value=mock.Mock(stdout="")):
            self.assertIn("error", api.speed_test("ping", "en0"))

    def test_live_reading_counts_samples(self):
        api = main.Api(lambda _: {})
        self.assertIsNone(api.speed_live())
        with mock.patch.dict(main.SPEED_TESTS, {"ping": lambda _, report: report(7) or 7}), \
                mock.patch("main.find_interface", return_value=("en0",)):
            self.assertEqual(api.speed_test("ping"), {"value": 7, "interface": "en0"})
        self.assertEqual(api.speed_live(), {"count": 1, "value": 7})


class Wifi(unittest.TestCase):
    @staticmethod
    def network(ssid, secure=True):
        network = mock.Mock()
        network.ssid.return_value = ssid
        network.rssiValue.return_value = -50
        network.wlanChannel.return_value.channelNumber.return_value = 36
        network.wlanChannel.return_value.channelBand.return_value = 2
        network.supportsSecurity_.side_effect = lambda security: not secure and security == main.WIFI_SECURITY_NONE
        return network

    def test_row_marks_connected_known_and_open(self):
        row = main.wifi_row(self.network("Home"), {"Home"}, "Home")
        self.assertEqual(row, {
            "ssid": "Home", "signal": -50, "channel": 36, "band": "5 GHz", "secure": True, "known": True, "current": True,
        })
        self.assertFalse(main.wifi_row(self.network("Cafe", secure=False), set(), "Home")["secure"])

    def test_hidden_name_is_never_marked_connected(self):
        row = main.wifi_row(self.network(None), set(), None)
        self.assertEqual((row["ssid"], row["current"], row["known"]), ("", False, False))

    def test_known_names_skip_the_heading(self):
        output = "Preferred networks on en0:\n\tHome\n\tCafé-5G\n"
        with mock.patch("subprocess.run", return_value=mock.Mock(stdout=output)):
            self.assertEqual(main.known_wifi("en0"), {"Home", "Café-5G"})


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

    def test_scan_error_is_passed_to_the_page(self):
        self.assertEqual(main.Api(lambda _: {"error": "denied"}).scan("en0"), {"error": "denied"})


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
