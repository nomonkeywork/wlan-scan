# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python app (`main.py`) showing a local HTML/WebGL page in a native macOS window through pywebview. Runs as the normal user: it reads devices from macOS's ARP table after sending to each address.

## Users

One person checking their own home network from their MacBook.

## Product Purpose

Show what is on the home network right now: who is online, what an unknown device is, and which IP and MAC it has. Success is answering "what is that device?" in one click.

## Positioning

A local tool with no account or cloud. It shows the network as a physical arrangement around the router, using the user's own names for their devices.

## Operating Context

A Starlink router is the gateway, with TP-Link extenders on the same subnet. An extender can answer ARP for its clients with its own MAC, so one MAC can stand for several real devices.

## Capabilities and Constraints

- ARP scan, vendor lookup from a bundled offline list, gateway detection and suspected-AP guess.
- Rename devices, stored by MAC in `names.json`.
- CSV export and network interface selection. Opening the network list refreshes it and scans again.
- 3D map and sortable table views. The table has one row per IP, with hostname (mDNS), ping and IPv6.
- Role override by MAC in `roles.json`, and opening a device's page in the browser.
- Speed test with macOS's `networkQuality`, on request only; the one feature that uses the internet.
- List of Wi-Fi networks in range through CoreWLAN.
- Everything else works offline. No assets loaded from the internet.
- Roles and vendors are guesses from data and must not be presented as certain.

## Brand Commitments

Design and colour come from the user's ffa project: JetBrains Mono for all text, Tailwind slate and indigo, and its card and dropdown patterns.

## Evidence on Hand

Real scan results only. No sample devices may appear in the shipped app.

## Product Principles

- Device facts stay readable and one click away; the 3D scene serves them.
- Show only what the scan found. An unknown device stays unknown until named.
- Device data stays on this Mac.
