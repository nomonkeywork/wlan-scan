# Freds LAN for macOS

A desktop app that shows your local network as a 3D map, with the router at the centre and every device around it, or as a sortable table. Click a device to see its details and give it a name.

## Setup

```sh
brew install python@3.12
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On Intel Macs, use `/usr/local/bin/python3.12`.

## Run

```sh
.venv/bin/python main.py
```

Run this from the project folder and use the venv's Python as shown. No password or `sudo` is needed: the app sends a small packet to every address, which makes macOS ask for each device over ARP, and then reads macOS's ARP table.

macOS asks once whether the app may access your local network. Allow it, or the scan can't reach anything. You can change this later in System Settings under Privacy & Security, then Local Network.

The app scans when it opens. Opening the network list refreshes the list and scans again, and choosing another network scans that one. **Scan** also scans again, **Map / Table / Speedtest / WLAN** switches views, and **Export CSV…** saves one row per IP.

### Reading the map

- **Indigo centre:** the default gateway reported by `netifaces`.
- **Bearing:** the rim is numbered in the last part of the IP, so a device at `.156` sits near `.160` and stays there when others join.
- **Height:** how many addresses the MAC answers on. A range extender can answer for its clients with its own MAC, so these may be several real devices. The table shows them per IP.
- **Blue, inner ring:** an access point. Without a role you chose, it's a guess: the MAC has the same vendor prefix as the router or comes from a networking vendor, and port 22, 80 or 443 is open.
- **Green:** this Mac.
- **Lighter name:** the hostname, vendor or "Unknown device", not a name you chose.
- **New:** the device wasn't in the previous scan since the app opened. The mark stays until you click the device.

Selecting a device draws an indigo line to the router. It means "on the same network" and doesn't show the real path, so a device connected through an extender still links straight to the router.

Drag to turn the chart and scroll to zoom. Esc clears the selection.

### The table

One row per IP, with name, IPv4, IPv6 local and global, MAC, hostname, ping, vendor and role. Click a column header to sort. Hostnames come from multicast DNS, so devices that don't publish a name stay blank. IPv6 addresses come from the Mac's neighbour table and only appear for devices it has recently talked to.

### Naming devices

Select a device, type a name and press **Save**. Leave the name empty to clear it. Names are saved by MAC address in `names.json` next to `main.py`, so they survive restarts and IP changes. A device that changes its randomized MAC shows up unnamed and needs naming again.

### Roles and opening devices

In a device's details, **Role** can be set to **Access point** or **Device**, or left on **Automatic**. Your choice is saved by MAC address in `roles.json`. The router and this Mac are detected, not guessed, so they can't be changed.

The icon beside an IP, in the details and in the table, opens `http://<ip>/` in your default browser.

### Speedtest

**Start test** measures download, upload and ping with `networkQuality`, which is built into macOS. It takes about a minute and sends test data over your internet connection to Apple's servers. Results aren't saved.

### WLAN

Lists the Wi-Fi networks in range with signal, band, channel and security, strongest first, and marks the one you're connected to and those saved on this Mac. macOS only reveals network names to apps allowed to use Location, so the app asks for that the first time you open this tab. The app doesn't use your location. Started from the terminal, names may stay hidden, so use the double-click app.

### Double-click app

```sh
sh build_app.sh
```

This creates `Freds LAN.app` in `~/Applications`, so Spotlight can find it and you can keep it in the Dock. It uses the `.venv` and files in this folder, so rebuild it if you move the folder. Started from the terminal, the window shows as Python in the Dock instead.

## Limitations

- A device that just left the network can stay listed for a few minutes, until macOS drops it from its ARP table.
- Only the local /24 is scanned on larger networks.
- Devices that are asleep, or on an isolated guest Wi-Fi, won't answer ARP and won't appear.
- Vendors registered after the bundled list was built show as Unknown.

## Offline use

The speed test is the only feature that uses the internet, and only when you start it. three.js and the JetBrains Mono font (SIL Open Font License) are bundled in `web/vendor`, and vendor names come from the list bundled with `mac-vendor-lookup`.

## Tests

No network scan needed:

```sh
.venv/bin/python -m unittest -v
```
