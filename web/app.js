import * as THREE from "three";
import { OrbitControls } from "./vendor/OrbitControls.js";

// The ffa project's palette: Tailwind slate and indigo, plus its chart colours.
const SLATE_300 = 0xcbd5e1;
const SLATE_400 = 0x94a3b8;
const SLATE_600 = 0x475569;
const INDIGO = 0x4f46e5;
const ROLE_COLOR = { "Router/Gateway": INDIGO, "Suspected AP": 0x0ea5e9, "Access point": 0x0ea5e9, "This Mac": 0x10b981 };
const ACCESS_POINT_ROLES = ["Suspected AP", "Access point"];

const PLATE_RADIUS = 12;
const FIT_RADIUS = 14.9;
const VIEW_LIFT = 0.075;
const ROUTER_REACH = 1.3;
const ROUTER_LIFT = 30;
const SWEEP_SECONDS = 2.4;
const TURN = Math.PI * 2;
const OCTETS = 256;
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const $ = (id) => document.getElementById(id);
const ui = {
  pulldown: $("pulldown"), network: $("network"), networkLabel: $("network-label"), networkMenu: $("network-menu"),
  scan: $("scan"), scanLabel: $("scan-label"), export: $("export"), status: $("status"),
  chart: $("chart"), canvas: $("sky"), labels: $("labels"), devices: $("devices"), count: $("count"),
  detail: $("detail"), detailEmpty: $("detail-empty"), name: $("name"), renameError: $("rename-error"),
  chartFoot: $("chart-foot"), tableView: $("table-view"), tableHead: $("table-head"), tableBody: $("table-body"),
  viewMap: $("view-map"), viewTable: $("view-table"), viewSpeed: $("view-speed"), speedView: $("speed-view"), viewWifi: $("view-wifi"), wifiView: $("wifi-view"), deviceList: $("device-list"), panel: $("panel"), leaders: $("leaders"),
};

const COLUMNS = [
  { key: "name", label: "Name" },
  { key: "ping", label: "Ping" },
  { key: "ip", label: "IPv4 address" },
  { key: "role", label: "Role" },
  { key: "mac", label: "MAC address" },
  { key: "hostname", label: "Hostname" },
  { key: "vendor", label: "Vendor" },
  { key: "ipv6Local", label: "IPv6 local" },
  { key: "ipv6Global", label: "IPv6 global" },
];

let api = null;
let devices = [];
let tableRows = [];
let sort = { key: "ip", direction: 1 };
let view = "map";
let interfaces = [];
let currentInterface = null;
let scanning = false;
let scanAgain = false;
let selectedMac = null;
let knownMacs = null;       // MACs from the previous scan; null until the first scan is done.
const newMacs = new Set();  // Marked until clicked, so a new device can't slip by unnoticed.
let sky = null;

// ---------- Map ----------

function line(points, opacity, color = SLATE_400) {
  return new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity }),
  );
}

function circle(radius, opacity, y = 0) {
  const points = [];
  for (let i = 0; i <= 128; i++) {
    const a = (i / 128) * TURN;
    points.push(new THREE.Vector3(Math.cos(a) * radius, y, Math.sin(a) * radius));
  }
  return line(points, opacity);
}

function octetAngle(octet) {
  return (octet / OCTETS) * TURN;
}

function rimNumeral(octet) {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 64;
  const context = canvas.getContext("2d");
  context.font = '600 30px "JetBrains Mono", Menlo, monospace';
  context.fillStyle = "#475569";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.fillText(`.${octet}`, 64, 32);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: texture, transparent: true, depthWrite: false, sizeAttenuation: false,
  }));
  const a = octetAngle(octet);
  sprite.position.set(Math.cos(a) * (PLATE_RADIUS + 1.25), 0, Math.sin(a) * (PLATE_RADIUS + 1.25));
  // Constant size on screen: these state addresses, so far ones must stay as readable as near ones.
  sprite.scale.set(0.06, 0.03, 1);
  return sprite;
}

function drawPlate() {
  const plate = new THREE.Group();

  // A white disc with real thickness, which catches the shadows of the devices above it.
  const thickness = 0.45;
  const disc = new THREE.Mesh(
    new THREE.CylinderGeometry(PLATE_RADIUS + 0.45, PLATE_RADIUS + 0.45, thickness, 128),
    [
      new THREE.MeshBasicMaterial({ color: 0xe2e8f0 }),
      new THREE.MeshBasicMaterial({ color: 0xffffff }),
      new THREE.MeshBasicMaterial({ color: 0xe2e8f0 }),
    ],
  );
  disc.position.y = -thickness / 2 - 0.02;
  plate.add(disc);
  const shadows = new THREE.Mesh(
    new THREE.CircleGeometry(PLATE_RADIUS + 0.45, 128).rotateX(-Math.PI / 2),
    new THREE.ShadowMaterial({ color: 0x0f172a, opacity: 0.16 }),
  );
  shadows.position.y = -0.01;
  shadows.receiveShadow = true;
  plate.add(shadows);

  for (const radius of [3, 6, 9]) plate.add(circle(radius, 0.45));
  plate.add(circle(PLATE_RADIUS, 0.9));

  // The rim reads in last IP octets, so a device's bearing states its address.
  for (let octet = 0; octet < OCTETS; octet += 4) {
    const a = octetAngle(octet);
    const dir = new THREE.Vector3(Math.cos(a), 0, Math.sin(a));
    const major = octet % 32 === 0;
    plate.add(line([dir.clone().multiplyScalar(PLATE_RADIUS + (major ? 0 : 0.26)), dir.clone().multiplyScalar(PLATE_RADIUS + 0.45)], 0.9));
    if (major) {
      plate.add(line([dir.clone().multiplyScalar(1.1), dir.clone().multiplyScalar(PLATE_RADIUS)], 0.28));
      plate.add(rimNumeral(octet));
    }
  }
  return plate;
}

function drawRouter(hub) {
  const spinner = new THREE.Group();
  const indigo = new THREE.MeshStandardMaterial({ color: INDIGO, roughness: 0.45, metalness: 0.1, emissive: INDIGO, emissiveIntensity: 0.18 });
  const core = new THREE.Mesh(new THREE.SphereGeometry(0.75, 48, 32), indigo);
  core.castShadow = true;
  spinner.add(core);
  const ring = new THREE.Mesh(new THREE.TorusGeometry(ROUTER_REACH, 0.04, 10, 128), indigo);
  ring.rotation.x = Math.PI / 2;
  spinner.add(ring);
  spinner.position.copy(hub);

  const mount = new THREE.Group();
  const foot = new THREE.Mesh(
    new THREE.RingGeometry(0.45, 0.6, 48).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: INDIGO, side: THREE.DoubleSide }),
  );
  mount.add(spinner, foot, line([hub, new THREE.Vector3(0, 0, 0)], 0.9, INDIGO));
  mount.visible = false; // Only appears once a scan has found the gateway.
  return mount;
}

function drawMeridian() {
  // A quarter arc from the plate's rim up over the router: the scan passing each bearing.
  const points = [];
  for (let i = 0; i <= 48; i++) {
    const t = (i / 48) * (Math.PI / 2);
    points.push(new THREE.Vector3(Math.cos(t) * (PLATE_RADIUS + 0.45), Math.sin(t) * 6.4, 0));
  }
  const meridian = new THREE.Group();
  meridian.add(new THREE.Mesh(
    new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 96, 0.035, 8),
    new THREE.MeshBasicMaterial({ color: INDIGO }),
  ));
  meridian.add(line([new THREE.Vector3(0, 0, 0), new THREE.Vector3(PLATE_RADIUS + 0.45, 0, 0)], 0.9, INDIGO));
  meridian.visible = false;
  return meridian;
}

function lastOctet(device) {
  return Number(device.ips[0].split(".").at(-1));
}

function ring(group, radius, placed) {
  // Bearing comes from the IP, so a device stays put when others join.
  // Close neighbours alternate between two radii so their labels can't collide.
  const minimumGap = 0.14;
  const closeGap = 0.5;
  let previous = -Infinity;
  let raised = false;
  [...group].sort((a, b) => lastOctet(a) - lastOctet(b)).forEach((device) => {
    const angle = Math.max(octetAngle(lastOctet(device)), previous + minimumGap);
    raised = angle - previous < closeGap && !raised;
    previous = angle;
    const r = radius + (raised ? 2.2 : 0);
    // Height shows how many addresses the device answers on.
    const y = 1 + Math.min(device.ips.length - 1, 4) * 0.65;
    placed.set(device.mac, { angle: angle % TURN, position: new THREE.Vector3(Math.cos(angle) * r, y, Math.sin(angle) * r) });
  });
}

function layout(list) {
  const placed = new Map();
  const others = list.filter((d) => d.role !== "Router/Gateway");
  ring(others.filter((d) => ACCESS_POINT_ROLES.includes(d.role)), 5, placed);
  ring(others.filter((d) => !ACCESS_POINT_ROLES.includes(d.role)), 8.4, placed);
  return placed;
}

function createSky() {
  const renderer = new THREE.WebGLRenderer({ canvas: ui.canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 400);
  camera.position.set(0, 19, 16.5);

  const controls = new OrbitControls(camera, ui.canvas);
  controls.enableDamping = true;
  controls.enablePan = false;
  controls.minDistance = 20;
  controls.maxDistance = 80;
  controls.minPolarAngle = 0.15;
  controls.maxPolarAngle = 1.4;
  controls.target.set(0, 0, 0);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xcbd5e1, 2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(5, 18, 7);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.radius = 6;
  Object.assign(sun.shadow.camera, { left: -15, right: 15, top: 15, bottom: -15, near: 1, far: 40 });
  scene.add(sun);

  const hub = new THREE.Vector3(0, 3, 0);
  const router = drawRouter(hub);
  const meridian = drawMeridian();
  const stars = new THREE.Group();
  scene.add(drawPlate(), router, meridian, stars);

  const state = {
    renderer, scene, camera, controls, router, meridian, stars, hub,
    items: new Map(), routerLabel: null, routerDevice: null, angle: 0, sweeping: false, revealing: false,
    focus: new THREE.Vector3(), clock: new THREE.Clock(),
  };

  const resize = () => {
    const { clientWidth: width, clientHeight: height } = ui.chart;
    if (!width || !height) return; // The map is hidden while the table is showing.
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    // The near half of a tilted plate looks larger, so lift the picture to even the margins.
    camera.setViewOffset(width, height, 0, height * VIEW_LIFT, width, height);
    // Keep the whole plate and its numerals in view at any window size.
    const halfHeight = Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    const distance = Math.max(FIT_RADIUS / (halfHeight * camera.aspect), (FIT_RADIUS * 0.86) / halfHeight);
    camera.position.sub(controls.target).setLength(distance).add(controls.target);
  };
  new ResizeObserver(resize).observe(ui.chart);
  resize();

  // A click on the empty map clears the selection; a drag only turns it.
  let downAt = null;
  ui.canvas.addEventListener("pointerdown", (event) => { downAt = [event.clientX, event.clientY]; });
  ui.canvas.addEventListener("pointerup", (event) => {
    if (downAt && Math.hypot(event.clientX - downAt[0], event.clientY - downAt[1]) < 4) select(null);
    downAt = null;
  });

  renderer.setAnimationLoop(() => frame(state));
  return state;
}

function isGuessedName(device) {
  return !device.name && device.role !== "Router/Gateway" && device.role !== "This Mac";
}

function displayName(device) {
  if (device.name) return device.name;
  if (device.role === "Router/Gateway") return "Router";
  if (device.role === "This Mac") return "This Mac";
  // With several IPs on one MAC, a hostname may belong to a client behind an extender.
  if (device.ips.length === 1 && device.hostnames[0]) return device.hostnames[0];
  if (/^(Unknown|Private)/.test(device.vendor)) return "Unknown device";
  return device.vendor;
}

function ipSummary(device) {
  return device.ips.length > 1 ? `${device.ips[0]} +${device.ips.length - 1}` : device.ips[0];
}

function createLabel() {
  const label = document.createElement("button");
  label.type = "button";
  label.className = "star-label";
  ui.labels.append(label);
  return label;
}

function fillLabel(label, device) {
  const dense = ui.labels.classList.contains("dense") && device.role !== "Router/Gateway";
  const chip = document.createElement("span");
  chip.className = "chip";
  const name = document.createElement("span");
  name.className = "label-name";
  // In a crowd, repeated vendor names answer nothing, but the address does.
  name.textContent = dense && !device.name ? `.${lastOctet(device)}` : displayName(device);
  name.classList.toggle("guess", isGuessedName(device) && !dense);
  chip.append(name);
  if (!dense) {
    const ip = document.createElement("span");
    ip.className = "label-ip";
    ip.textContent = ipSummary(device);
    chip.append(ip);
  }
  if (newMacs.has(device.mac)) {
    const mark = document.createElement("span");
    mark.className = "new-mark";
    mark.textContent = "New";
    chip.append(mark);
  }
  label.replaceChildren(chip);
  label.setAttribute("aria-label", `${displayName(device)}, ${device.role}, ${device.ips.join(", ")}`);
  label.setAttribute("aria-pressed", String(device.mac === selectedMac));
}

function createStar(device, placement, skyState) {
  const { position } = placement;
  const color = new THREE.Color(ROLE_COLOR[device.role] ?? SLATE_600);
  const group = new THREE.Group();
  group.position.copy(position);

  const material = new THREE.MeshStandardMaterial({ color, roughness: 0.55, emissive: color, emissiveIntensity: 0.12 });
  const addBody = (offset, size) => {
    const body = new THREE.Mesh(new THREE.SphereGeometry(size, 24, 16), material);
    body.position.copy(offset);
    body.castShadow = true;
    group.add(body);
    return body;
  };
  const body = addBody(new THREE.Vector3(), 0.28);

  // Each extra IP of the same MAC becomes a small point linked to the device,
  // on the router's side so the label on the outer side stays clear.
  const extras = device.ips.length - 1;
  let previous = new THREE.Vector3();
  for (let i = 0; i < extras; i++) {
    const a = placement.angle + Math.PI + (i - (extras - 1) / 2) * 0.75;
    const offset = new THREE.Vector3(Math.cos(a) * 1.25, 0.25 * (i % 2), Math.sin(a) * 1.25);
    addBody(offset, 0.1);
    group.add(line([previous, offset], 0.9, SLATE_400));
    previous = offset;
  }

  const foot = new THREE.Vector3(position.x, 0, position.z);
  const footRing = new THREE.Mesh(
    new THREE.RingGeometry(0.12, 0.18, 24).rotateX(-Math.PI / 2),
    new THREE.MeshBasicMaterial({ color: SLATE_400, transparent: true, opacity: 1, side: THREE.DoubleSide }),
  );
  footRing.position.copy(foot);
  const drop = line([position, foot], 0.9, SLATE_300);

  // The link to the router only appears for the selected device.
  const middle = skyState.hub.clone().add(position).multiplyScalar(0.5);
  middle.y += 1.3;
  const link = line(new THREE.QuadraticBezierCurve3(skyState.hub, middle, position).getPoints(48), 1, INDIGO);
  link.visible = false;

  const selectionRing = new THREE.Mesh(
    new THREE.TorusGeometry(0.58, 0.035, 8, 48),
    new THREE.MeshBasicMaterial({ color: INDIGO }),
  );
  selectionRing.visible = false;
  group.add(selectionRing);

  const parts = new THREE.Group();
  parts.add(group, footRing, drop, link);
  skyState.stars.add(parts);
  return {
    device, parts, group, link, drop, footRing, selectionRing, body, material, baseColor: color,
    reveal: 0, revealing: false, flare: 0, angle: placement.angle,
  };
}

function disposeItem(item, skyState) {
  skyState.stars.remove(item.parts);
  item.parts.traverse((object) => {
    object.geometry?.dispose();
    object.material?.dispose();
  });
  item.label.remove();
  item.leader.remove();
}

function renderSky(list, animate) {
  if (!sky) return;
  const previous = new Set(sky.items.keys());
  for (const item of sky.items.values()) disposeItem(item, sky);
  sky.items.clear();

  sky.router.visible = list.some((d) => d.role === "Router/Gateway");
  ui.labels.classList.toggle("dense", list.length > 14);
  const placements = layout(list);
  for (const device of list) {
    if (device.role === "Router/Gateway") {
      sky.routerLabel ??= createLabel();
      sky.routerLabel.classList.add("router");
      sky.routerLabel.onclick = () => select(device.mac);
      sky.routerDevice = device;
      continue;
    }
    const item = createStar(device, placements.get(device.mac), sky);
    item.leader = document.createElementNS("http://www.w3.org/2000/svg", "line");
    ui.leaders.append(item.leader);
    item.label = createLabel();
    item.label.onclick = () => select(device.mac);
    fillLabel(item.label, device);
    item.reveal = !animate || previous.has(device.mac) ? 1 : 0;
    applyReveal(item);
    sky.items.set(device.mac, item);
  }
  if (!list.some((d) => d.role === "Router/Gateway") && sky.routerLabel) {
    sky.routerLabel.remove();
    sky.routerLabel = null;
    sky.routerDevice = null;
  }
  refreshHighlights();
}

function applyReveal(item) {
  const t = 1 - (1 - item.reveal) ** 3;
  item.group.scale.setScalar(Math.max(t, 0.0001));
  item.drop.material.opacity = 0.9 * t;
  item.footRing.material.opacity = t;
  item.label.style.opacity = t;
  item.label.style.visibility = t > 0 ? "visible" : "hidden";
}

function refreshHighlights() {
  if (!sky) return;
  for (const item of sky.items.values()) {
    const selected = item.device.mac === selectedMac;
    item.selectionRing.visible = selected;
    item.link.visible = selected;
    fillLabel(item.label, item.device);
  }
  if (sky.routerLabel && sky.routerDevice) fillLabel(sky.routerLabel, sky.routerDevice);
  const target = sky.items.get(selectedMac);
  sky.focus.set(0, 0, 0);
  if (target) sky.focus.addScaledVector(target.group.position, 0.12).setY(0);
}

const projected = new THREE.Vector3();
const projectedHub = new THREE.Vector3();
const cameraUp = new THREE.Vector3();
const indigoColor = new THREE.Color(INDIGO);

function toScreen(vector, width, height) {
  return [(vector.x * 0.5 + 0.5) * width, (-vector.y * 0.5 + 0.5) * height];
}

function placeRouterLabel(state, width, height) {
  // Keep the router's name just below its rings and foot at any window size or zoom.
  const [x, y] = toScreen(projectedHub, width, height);
  cameraUp.setFromMatrixColumn(state.camera.matrixWorld, 1);
  projected.copy(state.hub).addScaledVector(cameraUp, -ROUTER_REACH).project(state.camera);
  const ringBottom = toScreen(projected, width, height)[1];
  projected.set(0, 0, 0).project(state.camera);
  const footBottom = toScreen(projected, width, height)[1] + 14;
  const nameOffset = Math.max(ringBottom, footBottom) - y + 6;
  state.routerLabel.style.paddingTop = `${ROUTER_LIFT + nameOffset}px`;
  state.routerLabel.style.transform = `translate(${x}px, ${y}px) translate(-50%, -${ROUTER_LIFT}px)`;
  const w = state.routerLabel.offsetWidth;
  return { left: x - w / 2, right: x + w / 2, top: y + nameOffset, bottom: y - ROUTER_LIFT + state.routerLabel.offsetHeight };
}

function placeStarLabels(state, width, height, placed) {
  const hubX = (projectedHub.x * 0.5 + 0.5) * width;
  const gap = 16; // The button's padding on the device's side.
  const boxes = [];
  // The rim numerals state addresses, so labels stay off them too.
  for (let octet = 0; octet < OCTETS; octet += 32) {
    const a = octetAngle(octet);
    projected.set(Math.cos(a) * (PLATE_RADIUS + 1.25), 0, Math.sin(a) * (PLATE_RADIUS + 1.25)).project(state.camera);
    const [x, y] = toScreen(projected, width, height);
    placed.push({ left: x - 22, right: x + 22, top: y - 10, bottom: y + 10 });
  }
  for (const item of state.items.values()) {
    projected.copy(item.group.position).project(state.camera);
    const visible = projected.z < 1 && item.reveal > 0;
    item.label.style.display = projected.z < 1 ? "" : "none";
    item.leader.style.display = "none";
    if (!visible) continue;
    const [x, y] = toScreen(projected, width, height);
    const w = item.label.offsetWidth;
    const h = item.label.offsetHeight;
    // Outer side of the device keeps it clear of the router, unless that runs off the map.
    let toLeft = x < hubX;
    if (toLeft && x - w < 4) toLeft = false;
    else if (!toLeft && x + w > width - 4) toLeft = true;
    boxes.push({ item, x, y, w, h, toLeft, top: y - h / 2 });
    // No label may sit on any device, or the map would name the wrong one.
    placed.push({ left: x - 11, right: x + 11, top: y - 11, bottom: y + 11 });
  }

  // Top to bottom, a label that would land on something moves just below it.
  boxes.sort((a, b) => a.top - b.top);
  const collides = (left, right, top, h) => placed.some((other) => (
    left < other.right && right > other.left && top < other.bottom && top + h > other.top
  ));
  const span = (box, toLeft) => (toLeft ? [box.x - box.w, box.x - gap] : [box.x + gap, box.x + box.w]);
  for (const box of boxes) {
    // Staying beside its own device beats everything, so try the other side before moving away.
    const [otherLeft, otherRight] = span(box, !box.toLeft);
    if (collides(...span(box, box.toLeft), box.top, box.h) && otherLeft >= 4 && otherRight <= width - 4
      && !collides(otherLeft, otherRight, box.top, box.h)) {
      box.toLeft = !box.toLeft;
    }
    const [left, right] = span(box, box.toLeft);
    for (let pass = 0, moved = true; moved && pass < 6; pass++) {
      moved = false;
      for (const other of placed) {
        if (left < other.right && right > other.left && box.top < other.bottom && box.top + box.h > other.top) {
          box.top = other.bottom + 2;
          moved = true;
        }
      }
    }
    placed.push({ left, right, top: box.top, bottom: box.top + box.h });
    box.item.label.classList.toggle("to-left", box.toLeft);
    box.item.label.style.transform = `translate(${box.toLeft ? box.x - box.w : box.x}px, ${box.top}px)`;
    // A moved label gets a line back to its device, so it can't be read as another's.
    if (Math.abs(box.top + box.h / 2 - box.y) > 3) {
      const { leader } = box.item;
      leader.style.display = "";
      leader.setAttribute("x1", box.x);
      leader.setAttribute("y1", box.y);
      leader.setAttribute("x2", box.toLeft ? right : left);
      leader.setAttribute("y2", box.top + box.h / 2);
    }
  }
}

function frame(state) {
  if (view !== "map") return;
  // Not clamped: a throttled background window should catch up, not crawl.
  const delta = state.clock.getDelta();

  let swept = null;
  if (state.sweeping) {
    const from = state.angle;
    state.angle += (delta / SWEEP_SECONDS) * TURN;
    swept = [from, state.angle];
    if (state.angle >= TURN) {
      state.angle -= TURN;
      if (state.revealing) {
        state.revealing = false;
        state.sweeping = false;
        state.meridian.visible = false;
      }
    }
    state.meridian.rotation.y = -state.angle;
  }

  for (const item of state.items.values()) {
    // Every device answers when the arc crosses it, on rescans too.
    if (swept && item.angle > swept[0] && item.angle <= swept[1]) {
      item.flare = 1;
      if (item.reveal < 1) item.revealing = true;
    }
    // A device the arc can no longer reach still has to appear.
    if (!state.sweeping && item.reveal < 1) item.revealing = true;
    if (item.revealing && item.reveal < 1) {
      item.reveal = Math.min(1, item.reveal + delta / 0.55);
      applyReveal(item);
    }
    if (item.flare > 0) {
      item.flare = Math.max(0, item.flare - delta / 0.7);
      item.body.scale.setScalar(1 + item.flare * 1.1);
      item.material.color.copy(item.baseColor).lerp(indigoColor, item.flare);
      item.material.emissive.copy(item.baseColor).lerp(indigoColor, item.flare);
    }
    if (item.selectionRing.visible) item.selectionRing.quaternion.copy(state.camera.quaternion);
  }

  state.controls.target.lerp(state.focus, reducedMotion ? 1 : 1 - Math.exp(-delta * 4));
  state.controls.update();
  state.renderer.render(state.scene, state.camera);

  const { clientWidth: width, clientHeight: height } = ui.chart;
  projectedHub.copy(state.hub).project(state.camera);
  const [hubX, hubY] = toScreen(projectedHub, width, height);
  cameraUp.setFromMatrixColumn(state.camera.matrixWorld, 1);
  projected.copy(state.hub).addScaledVector(cameraUp, ROUTER_REACH).project(state.camera);
  const reach = hubY - toScreen(projected, width, height)[1];
  // Labels stay off the router itself as well as off each other.
  const placed = [{ left: hubX - reach, right: hubX + reach, top: hubY - reach, bottom: hubY + reach }];
  if (state.routerLabel) placed.push(placeRouterLabel(state, width, height));
  placeStarLabels(state, width, height, placed);
}

function startSweep() {
  if (!sky || reducedMotion) return;
  sky.revealing = false;
  sky.angle = 0;
  sky.sweeping = true;
  sky.meridian.visible = true;
}

// One last turn reveals the new devices. Results never wait for it: a covered window
// gets throttled or no animation frames at all.
function revealWithSweep() {
  if (!sky?.sweeping) return;
  sky.angle = 0;
  sky.revealing = true;
}

function stopSweep() {
  if (!sky) return;
  sky.sweeping = false;
  sky.revealing = false;
  sky.meridian.visible = false;
}

// ---------- Panel ----------

function ipValue(ip) {
  return ip.split(".").reduce((sum, part) => sum * 256 + Number(part), 0);
}

function sortedDevices() {
  const order = (d) => (d.role === "Router/Gateway" ? 0 : 1);
  return [...devices].sort((a, b) => order(a) - order(b) || ipValue(a.ips[0]) - ipValue(b.ips[0]));
}

function dotClass(role) {
  return { "Router/Gateway": "router", "Suspected AP": "ap", "Access point": "ap", "This Mac": "mac" }[role] ?? "";
}

function renderList() {
  ui.devices.classList.toggle("is-empty", !devices.length);
  ui.chartFoot.hidden = !devices.length || !sky;
  ui.detailEmpty.hidden = !devices.length || Boolean(selectedMac);
  ui.devices.replaceChildren(...sortedDevices().map((device) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "device-row";
    if (device.mac === selectedMac) button.setAttribute("aria-current", "true");
    button.addEventListener("click", () => select(device.mac));

    const dot = document.createElement("span");
    dot.className = `dot ${dotClass(device.role)}`;
    const name = document.createElement("span");
    name.className = "row-name";
    name.classList.toggle("unnamed", !device.name);
    name.textContent = displayName(device);
    const ip = document.createElement("span");
    ip.className = "row-ip";
    ip.textContent = ipSummary(device);
    button.append(dot, name);
    if (newMacs.has(device.mac)) {
      const mark = document.createElement("span");
      mark.className = "row-new";
      mark.textContent = "New";
      button.append(mark);
    }
    button.append(ip);

    const row = document.createElement("li");
    row.append(button);
    return row;
  }));
  ui.count.textContent = devices.length ? String(devices.length) : "";
}

function openButton(ip) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "open-button";
  button.title = `Open ${ip} in browser`;
  button.setAttribute("aria-label", `Open ${ip} in browser`);
  button.insertAdjacentHTML("beforeend", '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>');
  button.addEventListener("click", async (event) => {
    event.stopPropagation();
    const result = await api.open_in_browser(ip);
    if (result.error) ui.status.textContent = result.error;
  });
  return button;
}

function roleText(role) {
  return role === "Suspected AP" ? "Suspected access point (a guess)" : role;
}

function renderRole(device) {
  // The router and this Mac are detected facts, so they show as plain text.
  $("role-text-label").hidden = !device.roleFixed;
  $("d-role-text").hidden = !device.roleFixed;
  $("role-field").hidden = device.roleFixed;
  $("d-role-text").textContent = roleText(device.role);
  for (const button of $("role-switch").children) {
    button.setAttribute("aria-pressed", String(button.dataset.role === device.roleOverride));
  }
  $("role-detected").textContent = `Detected: ${roleText(device.detectedRole)}`;
}

function applyListing(result) {
  devices = result.devices;
  tableRows = result.table;
  renderSky(devices, false);
  renderList();
  renderDetail();
  renderTable();
}

async function saveRole(role) {
  const result = await api.set_role(selectedMac, role);
  if (result.error) {
    ui.renameError.textContent = `The role wasn't saved: ${result.error}`;
    ui.renameError.hidden = false;
    return;
  }
  applyListing(result);
  ui.status.textContent = "Role saved";
}

function renderDetail() {
  const device = devices.find((d) => d.mac === selectedMac);
  ui.detail.hidden = !device;
  ui.renameError.hidden = true;
  if (!device) return;
  ui.name.value = device.name;
  $("ips-label").textContent = device.ips.length > 1 ? "IPs" : "IP";
  $("d-ips").replaceChildren(...device.ips.map((ip) => {
    const line = document.createElement("div");
    line.className = "ip-line";
    const text = document.createElement("span");
    text.textContent = ip;
    line.append(text, openButton(ip));
    return line;
  }));
  $("d-mac").textContent = device.mac;
  $("d-hostname").textContent = device.hostnames.join(", ") || "None found";
  $("d-ipv6").textContent = device.ipv6.join(", ") || "None found";
  $("d-vendor").textContent = device.vendor;
  renderRole(device);
}

function compareRows(a, b) {
  if (sort.key === "ip") return ipValue(a.ip) - ipValue(b.ip);
  if (sort.key === "ping") return Number(b.ping === true) - Number(a.ping === true);
  // Blank cells stay at the bottom in both directions.
  const [left, right] = [String(a[sort.key] ?? ""), String(b[sort.key] ?? "")];
  if (!left || !right) return (Number(!left) - Number(!right)) * sort.direction;
  return left.localeCompare(right, undefined, { sensitivity: "base", numeric: true });
}

function renderTable() {
  ui.tableHead.replaceChildren(...COLUMNS.map(({ key, label }) => {
    const th = document.createElement("th");
    th.scope = "col";
    const sorted = sort.key === key;
    th.setAttribute("aria-sort", sorted ? (sort.direction > 0 ? "ascending" : "descending") : "none");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    if (sorted) button.insertAdjacentHTML("beforeend", '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m18 15-6-6-6 6"/></svg>');
    button.dataset.sort = key;
    button.addEventListener("click", () => {
      sort = { key, direction: sorted ? -sort.direction : 1 };
      renderTable();
      // Rendering replaces the buttons, so keep keyboard users where they were.
      ui.tableHead.querySelector(`[data-sort="${key}"]`).focus();
    });
    th.append(button);
    return th;
  }));

  const rows = [...tableRows].sort((a, b) => compareRows(a, b) * sort.direction);
  ui.tableBody.replaceChildren(...rows.map((row) => {
    const tr = document.createElement("tr");
    tr.setAttribute("aria-selected", String(row.mac.toLowerCase() === selectedMac));
    tr.addEventListener("click", () => {
      select(row.mac.toLowerCase());
      ui.tableBody.querySelector(`[data-ip="${row.ip}"]`)?.focus();
    });
    for (const { key } of COLUMNS) {
      const td = document.createElement("td");
      if (key === "ping") {
        const dot = document.createElement("span");
        const state = row.ping === true ? "up" : row.ping === false ? "down" : "unknown";
        dot.className = `ping ${state}`;
        dot.setAttribute("role", "img");
        dot.setAttribute("aria-label", { up: "Answers ping", down: "No ping answer", unknown: "Ping unknown" }[state]);
        td.append(dot);
      } else if (key === "name") {
        // A real button gives keyboard users a way to select the row.
        td.className = "cell-name";
        const button = document.createElement("button");
        button.type = "button";
        // The same words as the map and the list; each row's own hostname has its own column.
        const device = devices.find((d) => d.mac === row.mac.toLowerCase());
        button.textContent = device ? displayName(device) : row.ip;
        button.dataset.ip = row.ip;
        td.append(button);
      } else if (key === "ip") {
        td.className = "cell-ip";
        const line = document.createElement("div");
        line.className = "ip-line";
        const text = document.createElement("span");
        text.textContent = row.ip;
        line.append(text, openButton(row.ip));
        td.append(line);
      } else {
        td.textContent = row[key] ?? "";
        td.title = row[key] ?? "";
      }
      tr.append(td);
    }
    return tr;
  }));
}

// The table is wide, so in that view the panel only appears for a selected device.
function syncPanel() {
  ui.panel.hidden = view === "speed" || view === "wifi" || (view === "table" && !selectedMac);
}

function setView(next) {
  view = next;
  const table = view === "table";
  ui.chart.hidden = view !== "map";
  ui.speedView.hidden = view !== "speed";
  ui.wifiView.hidden = view !== "wifi";
  ui.tableView.hidden = !table;
  ui.deviceList.hidden = view !== "map";
  syncPanel();
  ui.viewMap.setAttribute("aria-pressed", String(view === "map"));
  ui.viewSpeed.setAttribute("aria-pressed", String(view === "speed"));
  ui.viewWifi.setAttribute("aria-pressed", String(view === "wifi"));
  ui.viewTable.setAttribute("aria-pressed", String(table));
  if (table) renderTable();
  if (view === "wifi" && !wifiScanned) runWifiScan();
  try {
    localStorage.setItem("lan-scanner-view", view);
  } catch {
    // Remembering the view is only a convenience.
  }
}

function select(mac) {
  selectedMac = mac;
  newMacs.delete(mac);
  refreshHighlights();
  renderList();
  renderDetail();
  renderTable();
  syncPanel();
}

function showNotice(title, text) {
  $("notice-title").textContent = title;
  $("notice-text").textContent = text;
  $("notice").hidden = false;
}

// ---------- Speed test ----------

async function runSpeedTest() {
  if (!api) return;
  const start = $("speed-start");
  const status = $("speed-status");
  start.disabled = true;
  start.textContent = "Testing…";
  status.classList.remove("error");
  status.textContent = "Measuring download, then upload. This takes about a minute.";
  let result;
  try {
    result = await api.speed_test(currentInterface);
  } catch (error) {
    result = { error: String(error) };
  }
  start.disabled = false;
  start.textContent = "Test again";
  const failed = Boolean(result.error);
  $("speed-download").textContent = failed ? "–" : result.download.toFixed(1);
  $("speed-upload").textContent = failed ? "–" : result.upload.toFixed(1);
  $("speed-ping").textContent = failed ? "–" : Math.round(result.ping);
  status.classList.toggle("error", failed);
  status.textContent = failed ? result.error : `Measured at ${new Date().toLocaleTimeString()} through ${result.interface}, against Apple's servers.`;
}

// ---------- WLAN ----------

let wifiScanned = false;

function renderWifi(networks) {
  $("wifi-body").replaceChildren(...networks.map((network) => {
    const row = document.createElement("tr");
    const cells = [
      network.ssid || "Name hidden",
      `${network.signal} dBm`,
      network.band,
      network.channel,
      network.secure ? "Secured" : "Open",
      network.current ? "Connected" : network.known ? "Known" : "",
    ];
    for (const value of cells) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    return row;
  }));
}

async function runWifiScan() {
  if (!api) return;
  wifiScanned = true;
  const refresh = $("wifi-refresh");
  const status = $("wifi-status");
  refresh.disabled = true;
  status.classList.remove("error");
  status.textContent = "Looking for networks…";
  let result;
  try {
    result = await api.wifi();
  } catch (error) {
    result = { error: String(error) };
  }
  refresh.disabled = false;
  renderWifi(result.networks ?? []);
  status.classList.toggle("error", Boolean(result.error));
  status.textContent = result.error ?? (result.namesHidden
    ? "macOS hides network names until you allow Location. Open System Settings, then Privacy & Security, then Location Services, turn on Freds LAN, and refresh."
    : `${result.networks.length} networks in range`);
}

// ---------- Network pulldown ----------

function interfaceLabel({ name, ip }) {
  return `${name} (${ip})`;
}

function renderPulldown() {
  const current = interfaces.find(({ name }) => name === currentInterface);
  ui.networkLabel.textContent = current ? interfaceLabel(current) : "No network";
  ui.networkMenu.replaceChildren(...interfaces.map((entry) => {
    const option = document.createElement("li");
    option.id = `network-${entry.name}`;
    option.role = "option";
    option.dataset.name = entry.name;
    const selected = entry.name === currentInterface;
    option.setAttribute("aria-selected", String(selected));
    option.classList.toggle("active", selected);
    const text = document.createElement("span");
    text.textContent = interfaceLabel(entry);
    option.append(text);
    if (selected) {
      option.insertAdjacentHTML("beforeend", '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>');
    }
    option.addEventListener("mouseenter", () => setActiveOption(option));
    option.addEventListener("click", () => chooseInterface(entry.name));
    return option;
  }));
}

function setActiveOption(option) {
  for (const other of ui.networkMenu.children) other.classList.toggle("active", other === option);
  if (option) ui.networkMenu.setAttribute("aria-activedescendant", option.id);
}

function closePulldown(returnFocus = true) {
  if (ui.networkMenu.hidden) return;
  ui.networkMenu.hidden = true;
  ui.network.setAttribute("aria-expanded", "false");
  if (returnFocus) ui.network.focus();
}

// Opening the list refreshes the networks and scans again.
async function openPulldown() {
  ui.networkMenu.hidden = false;
  ui.network.setAttribute("aria-expanded", "true");
  ui.networkMenu.focus();
  setActiveOption(ui.networkMenu.querySelector('[aria-selected="true"]'));
  if (await refreshInterfaces()) runScan();
}

function chooseInterface(name) {
  const changed = name !== currentInterface;
  currentInterface = name;
  renderPulldown();
  closePulldown();
  if (!changed) return;
  // A different network: nothing on it is "new" compared with the last one.
  knownMacs = null;
  newMacs.clear();
  selectedMac = null;
  runScan();
}

function onMenuKey(event) {
  const options = [...ui.networkMenu.children];
  const index = options.findIndex((option) => option.classList.contains("active"));
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    const step = event.key === "ArrowDown" ? 1 : -1;
    setActiveOption(options[(index + step + options.length) % options.length]);
  } else if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    if (options[index]) chooseInterface(options[index].dataset.name);
  } else if (event.key === "Escape" || event.key === "Tab") {
    event.stopPropagation();
    closePulldown(event.key === "Escape");
  }
}

// ---------- Actions ----------

function setBusy(busy) {
  scanning = busy;
  ui.scan.disabled = busy || !currentInterface;
  ui.scan.setAttribute("aria-busy", String(busy));
  ui.scanLabel.textContent = busy ? "Scanning…" : "Scan";
  ui.export.disabled = busy || !devices.length;
}

async function refreshInterfaces() {
  interfaces = await api.interfaces();
  if (!interfaces.some(({ name }) => name === currentInterface)) currentInterface = interfaces[0]?.name ?? null;
  renderPulldown();
  ui.scan.disabled = scanning || !interfaces.length;
  if (!interfaces.length) {
    ui.status.textContent = "No network";
    showNotice("No active network", "Connect to Wi-Fi or Ethernet, then open the network list again.");
  }
  return interfaces.length > 0;
}

async function runScan() {
  // A scan is already running, so run one more for the latest choice when it ends.
  if (scanning) {
    scanAgain = true;
    return;
  }
  setBusy(true);
  // Without WebGL the notice explaining the missing map has to stay up.
  if (sky) $("notice").hidden = true;
  ui.status.textContent = `Scanning ${currentInterface}…`;
  startSweep();

  const scanned = currentInterface;
  let result;
  try {
    result = await api.scan(scanned);
  } catch (error) {
    result = { error: String(error) };
  }

  // The network changed while this ran, so its result belongs to the old one.
  if (scanned !== currentInterface) {
    stopSweep();
    scanAgain = true;
  } else if (result.error) {
    stopSweep();
    ui.status.textContent = "Scan failed";
    showNotice("The scan failed", result.error);
  } else {
    const macs = new Set(result.devices.map((d) => d.mac));
    if (knownMacs) for (const mac of macs) if (!knownMacs.has(mac)) newMacs.add(mac);
    for (const mac of [...newMacs]) if (!macs.has(mac)) newMacs.delete(mac);
    knownMacs = macs;

    devices = result.devices;
    tableRows = result.table;
    if (selectedMac && !macs.has(selectedMac)) selectedMac = null;
    renderSky(devices, !reducedMotion);
    revealWithSweep();
    renderList();
    renderDetail();
    renderTable();
    const count = devices.length === 1 ? "1 device" : `${devices.length} devices`;
    const addresses = tableRows.length !== devices.length ? `, ${tableRows.length} addresses` : "";
    ui.status.textContent = `${count}${addresses} on ${result.network} (${result.interface})`;
  }
  setBusy(false);

  if (scanAgain) {
    scanAgain = false;
    runScan();
  }
}

async function saveName(event) {
  event.preventDefault();
  const mac = selectedMac;
  const result = await api.rename(mac, ui.name.value);
  if (result.error) {
    ui.renameError.textContent = `The name wasn't saved: ${result.error}`;
    ui.renameError.hidden = false;
    return;
  }
  applyListing(result);
  ui.status.textContent = ui.name.value.trim() ? `Saved the name ${ui.name.value.trim()}` : "Name cleared";
}

async function exportCsv() {
  const result = await api.export();
  if (result.error) ui.status.textContent = `Export failed: ${result.error}`;
  else if (result.saved) ui.status.textContent = `Saved ${result.saved}`;
}

async function start(readyApi) {
  api = readyApi;
  // The rim numerals are drawn to a canvas, so their font has to be ready first.
  await document.fonts.load('500 32px "JetBrains Mono"').catch(() => {});
  try {
    sky = createSky();
  } catch {
    // The device list keeps working without WebGL.
    showNotice("The 3D map can't start", "WebGL isn't available in this window. The table still works.");
    ui.canvas.hidden = true;
    ui.viewMap.disabled = true;
  }
  ui.scan.addEventListener("click", runScan);
  ui.viewMap.addEventListener("click", () => setView("map"));
  ui.viewTable.addEventListener("click", () => setView("table"));
  ui.viewSpeed.addEventListener("click", () => setView("speed"));
  ui.viewWifi.addEventListener("click", () => setView("wifi"));
  $("speed-start").addEventListener("click", runSpeedTest);
  $("wifi-refresh").addEventListener("click", runWifiScan);
  let savedView = null;
  try {
    savedView = localStorage.getItem("lan-scanner-view");
  } catch {
    // Storage can be blocked; the map is a fine default.
  }
  // Without WebGL the table is the only way to see everything.
  setView(!sky || savedView === "table" ? "table" : "map");
  ui.export.addEventListener("click", exportCsv);
  ui.network.addEventListener("click", () => (ui.networkMenu.hidden ? openPulldown() : closePulldown()));
  ui.networkMenu.addEventListener("keydown", onMenuKey);
  document.addEventListener("pointerdown", (event) => {
    if (!ui.pulldown.contains(event.target)) closePulldown(false);
  });
  $("rename").addEventListener("submit", saveName);
  for (const button of $("role-switch").children) {
    button.addEventListener("click", () => saveRole(button.dataset.role));
  }
  renderList();
  addEventListener("keydown", (event) => {
    if (event.key === "Escape" && selectedMac) select(null);
  });
  if (await refreshInterfaces()) runScan();
}

// window.pywebview.api can exist before its methods are attached, so wait for a method itself.
function whenApiReady() {
  return new Promise((resolve) => {
    const check = () => (window.pywebview?.api?.interfaces ? resolve(window.pywebview.api) : setTimeout(check, 50));
    check();
  });
}

const stuck = setTimeout(() => showNotice("The app isn't responding", "Quit this window and start the app again."), 10000);
whenApiReady().then((ready) => {
  clearTimeout(stuck);
  $("notice").hidden = true;
  return start(ready);
}).catch((error) => showNotice("The app couldn't start", String(error)));
