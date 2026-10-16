// Varda's 3D terrain viewer: a DEM as a lit, shadowed mesh with a draped
// image. The same page runs inside Varda (Qt WebEngine) and as an exported,
// self-contained web page. Its data is window.VARDA_SCENE (see
// varda/terrain/scene.py); Varda drives it through window.viewer.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const scene = window.VARDA_SCENE;
const settings = Object.assign(
  {
    exaggeration: 1,
    sunAzimuth: 315,
    sunElevation: 35,
    shadows: true,
    background: "#101418",
    ambient: 0.35,
    sides: false, // a block diagram: walls down to a base
    baseDepth: 0, // below the lowest point, in height units (0: a quarter of the relief)
    sideColor: "#a08e78",
    edges: "smooth", // the outline: "smooth" (cut diagonally), "stepped" or "rectangle" (trimmed in Varda)
    northArrow: true,
    scaleBar: true, // measured at the view's center (the orbit target)
    colorBar: true, // when the drape is colored by elevation
  },
  scene.settings || {}
);

const container = document.getElementById("view");
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
} catch (error) {
  // Varda reads this from the console (no WebGL here: an old GPU or driver)
  console.log("varda:error " + error.message);
  document.body.insertAdjacentHTML("beforeend",
    "<p style='color:#ccc;padding:2em'>This view needs WebGL 2, which isn't available here.</p>");
  throw error;
}
renderer.setPixelRatio(window.devicePixelRatio || 1);
renderer.setSize(container.clientWidth, container.clientHeight);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.appendChild(renderer.domElement);

const world = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 1, 1e8);
camera.up.set(0, 0, 1); // z is up: x east, y north, as on a map

// --- the terrain -----------------------------------------------------------

function decodeHeights(base64, count) {
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  return new Uint16Array(bytes.buffer, 0, count);
}

const cols = scene.cols, rows = scene.rows;
const quantized = decodeHeights(scene.heights, cols * rows);
const zMid = scene.zMin + (scene.zStep * 65534) / 2; // keep coordinates small
const positions = new Float32Array(cols * rows * 3);
const uvs = new Float32Array(cols * rows * 2);
let zLow = Infinity, zHigh = -Infinity;
for (let r = 0; r < rows; r++) {
  for (let c = 0; c < cols; c++) {
    const i = r * cols + c, q = quantized[i];
    const z = q === 0 ? NaN : scene.zMin + (q - 1) * scene.zStep - zMid;
    positions[3 * i] = (c / (cols - 1) - 0.5) * scene.widthM;
    positions[3 * i + 1] = (0.5 - r / (rows - 1)) * scene.heightM;
    positions[3 * i + 2] = Number.isNaN(z) ? 0 : z;
    uvs[2 * i] = c / (cols - 1);
    uvs[2 * i + 1] = 1 - r / (rows - 1);
    if (!Number.isNaN(z)) { zLow = Math.min(zLow, z); zHigh = Math.max(zHigh, z); }
  }
}
// Two triangles per cell with four heights; with smooth edges, one per cell
// with three (the outline steps at 45° rather than in a staircase), as
// varda/terrain/solid.py builds for printing
let indices = [];
function buildIndices(smooth) {
  indices = [];
  for (let r = 0; r < rows - 1; r++) {
    for (let c = 0; c < cols - 1; c++) {
      const a = r * cols + c, b = a + 1, d = a + cols, e = d + 1;
      const has = [quantized[a], quantized[b], quantized[d], quantized[e]].map(Boolean);
      const count = has.filter(Boolean).length;
      if (count === 4) indices.push(a, d, b, b, d, e);
      else if (smooth && count === 3) {
        if (!has[0]) indices.push(b, d, e);
        else if (!has[1]) indices.push(a, d, e);
        else if (!has[2]) indices.push(a, e, b);
        else indices.push(a, d, b);
      }
    }
  }
}
// The surface's outline: its edges that no other triangle shares (a cell's
// side whose neighbor isn't solid, a three-cornered cell's diagonal), as
// [p, q, p, q, ...] in the order the triangles wind
function outline(smooth) {
  const edges = [];
  const need = smooth ? 3 : 4; // corners a solid cell has
  const corners = (r, c) => {
    const a = r * cols + c;
    return [quantized[a], quantized[a + 1], quantized[a + cols], quantized[a + cols + 1]].map(Boolean);
  };
  const solid = (r, c) => r >= 0 && c >= 0 && r < rows - 1 && c < cols - 1 &&
    corners(r, c).filter(Boolean).length >= need;
  for (let r = 0; r < rows - 1; r++) {
    for (let c = 0; c < cols - 1; c++) {
      if (!solid(r, c)) continue;
      const [ha, hb, hd, he] = corners(r, c);
      const a = r * cols + c, b = a + 1, d = a + cols, e = d + 1;
      if (ha && hb && !solid(r - 1, c)) edges.push(b, a);
      if (hd && he && !solid(r + 1, c)) edges.push(d, e);
      if (ha && hd && !solid(r, c - 1)) edges.push(a, d);
      if (hb && he && !solid(r, c + 1)) edges.push(e, b);
      if (!ha) edges.push(b, d);
      else if (!hb) edges.push(e, a);
      else if (!hd) edges.push(a, e);
      else if (!he) edges.push(d, b);
    }
  }
  return edges;
}

// Smooth edges: each outline point drawn toward its neighbors along the
// outline, by at most half a cell, so it runs smoothly rather than in 45°
// steps (points on the grid's border, or where the outline passes twice,
// stay); as varda/terrain/solid.py does for printing
const gridPositions = positions.slice();
function relaxOutline(edges, smooth) {
  positions.set(gridPositions);
  if (!smooth) return;
  const count = rows * cols, after = new Int32Array(count).fill(-1), before = new Int32Array(count).fill(-1);
  const twice = new Uint8Array(count);
  for (let k = 0; k < edges.length; k += 2) {
    const p = edges[k], q = edges[k + 1];
    if (after[p] >= 0) twice[p] = 1;
    after[p] = q;
    before[q] = p;
  }
  const moving = [];
  for (let k = 0; k < edges.length; k += 2) {
    const p = edges[k], r = Math.floor(p / cols), c = p % cols;
    if (!twice[p] && before[p] >= 0 && r > 0 && c > 0 && r < rows - 1 && c < cols - 1) moving.push(p);
  }
  const limitX = scene.widthM / (cols - 1) / 2, limitY = scene.heightM / (rows - 1) / 2;
  const next = new Float32Array(moving.length * 2);
  for (let round = 0; round < 8; round++) {
    moving.forEach((p, k) => {
      for (const [axis, limit] of [[0, limitX], [1, limitY]]) {
        const middle = (positions[3 * before[p] + axis] + positions[3 * after[p] + axis]) / 2;
        const step = positions[3 * p + axis] + 0.5 * (middle - positions[3 * p + axis]);
        const start = gridPositions[3 * p + axis];
        next[2 * k + axis] = Math.min(Math.max(step, start - limit), start + limit);
      }
    });
    moving.forEach((p, k) => { positions[3 * p] = next[2 * k]; positions[3 * p + 1] = next[2 * k + 1]; });
  }
}

let outlineEdges = outline(settings.edges !== "stepped");
buildIndices(settings.edges !== "stepped");
relaxOutline(outlineEdges, settings.edges !== "stepped");
const geometry = new THREE.BufferGeometry();
geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
geometry.setAttribute("uv", new THREE.BufferAttribute(uvs, 2));
geometry.setIndex(indices); // three.js picks 32-bit indices when needed
geometry.computeVertexNormals();

const material = new THREE.MeshStandardMaterial({ roughness: 0.95, metalness: 0 });
const terrain = new THREE.Mesh(geometry, material);
terrain.castShadow = true;
terrain.receiveShadow = true;
world.add(terrain);

const loader = new THREE.TextureLoader();
function loadTexture(url) {
  return new Promise((resolve) => loader.load(url, (texture) => {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    resolve(texture);
  }));
}

const textures = [];
if (scene.texture) {
  textures.push(loadTexture(scene.texture).then((texture) => {
    material.map = texture;
    material.needsUpdate = true;
  }));
} else {
  material.color.set("#b8b0a4");
}

// Overlays: images draped over part of the DEM, each its own layer (the
// same surface, drawn just in front of the one below) with its own opacity
const overlays = (scene.overlays || []).map((overlay, index) => {
  const layer = new THREE.MeshStandardMaterial({
    roughness: 0.95, metalness: 0, transparent: true, depthWrite: false,
    opacity: overlay.opacity ?? 1,
    polygonOffset: true, polygonOffsetFactor: -2 * (index + 1), polygonOffsetUnits: -2 * (index + 1),
  });
  const mesh = new THREE.Mesh(geometry, layer);
  mesh.receiveShadow = true;
  mesh.visible = overlay.visible ?? true;
  mesh.renderOrder = index + 1;
  terrain.add(mesh); // so it follows the exaggeration
  const [west, south, east, north] = overlay.uvBounds;
  textures.push(loadTexture(overlay.texture).then((texture) => {
    // the texture covers only its bounds; its clear border clamps outside them
    texture.wrapS = texture.wrapT = THREE.ClampToEdgeWrapping;
    texture.repeat.set(1 / (east - west), 1 / (north - south));
    texture.offset.set(-west / (east - west), -south / (north - south));
    layer.map = texture;
    layer.needsUpdate = true;
  }));
  return { mesh, layer };
});
const textureReady = Promise.all(textures);

// --- sides (a block diagram) -----------------------------------------------------

// A wall stands on every edge of the outline (as varda/terrain/solid.py
// builds for printing)
const sideMaterial = new THREE.MeshStandardMaterial({ roughness: 1, metalness: 0, side: THREE.DoubleSide });
let sides = null;
function buildSides() {
  if (sides) { terrain.remove(sides); sides.geometry.dispose(); sides = null; }
  if (!settings.sides) return;
  const depth = settings.baseDepth > 0 ? settings.baseDepth : Math.max((zHigh - zLow) * 0.25, 1);
  const baseZ = zLow - depth;
  const walls = [];
  const wall = (p, q) => { // under the surface's edge p → q (as its triangles wind)
    const [px, py, pz] = [positions[3 * p], positions[3 * p + 1], positions[3 * p + 2]];
    const [qx, qy, qz] = [positions[3 * q], positions[3 * q + 1], positions[3 * q + 2]];
    walls.push(qx, qy, qz, px, py, pz, px, py, baseZ, qx, qy, qz, px, py, baseZ, qx, qy, baseZ);
  };
  for (let k = 0; k < outlineEdges.length; k += 2) wall(outlineEdges[k], outlineEdges[k + 1]);
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(walls, 3));
  geometry.computeVertexNormals();
  sides = new THREE.Mesh(geometry, sideMaterial);
  sides.castShadow = true;
  sides.receiveShadow = true;
  terrain.add(sides); // follows the exaggeration
}

// --- lines draped on the surface (a traverse, mapped contacts) ------------------------

// Height at (u, v), fractions of the DEM's extent (v north), between grid
// points; NaN off the data
function heightAt(u, v) {
  const x = u * (cols - 1), y = (1 - v) * (rows - 1);
  const c = Math.min(Math.max(Math.floor(x), 0), cols - 2), r = Math.min(Math.max(Math.floor(y), 0), rows - 2);
  const fx = x - c, fy = y - r;
  const at = (rr, cc) => quantized[rr * cols + cc] ? positions[3 * (rr * cols + cc) + 2] : NaN;
  return at(r, c) * (1 - fx) * (1 - fy) + at(r, c + 1) * fx * (1 - fy) +
    at(r + 1, c) * (1 - fx) * fy + at(r + 1, c + 1) * fx * fy;
}

const lineLayers = (scene.lines || []).map((layer) => {
  const group = new THREE.Group();
  group.visible = layer.visible ?? true;
  world.add(group);
  // a little of their own light, so their color reads in shadow too
  const material = new THREE.MeshStandardMaterial({ color: layer.color, roughness: 0.6 });
  material.emissive.set(layer.color).multiplyScalar(0.35);
  return { layer, group, material };
});

function buildLines() {
  const step = 1 / Math.max(cols, rows); // about a grid cell between samples
  const lift = extent * 0.0015, radius = extent * 0.0025;
  for (const { layer, group, material } of lineLayers) {
    for (const child of [...group.children]) { group.remove(child); child.geometry.dispose(); }
    for (const path of layer.paths) {
      // densify, follow the surface, and split where there's no data
      let run = [];
      const flush = () => {
        if (run.length >= 2) {
          const curve = new THREE.CatmullRomCurve3(run, false, "centripetal");
          const tube = new THREE.TubeGeometry(curve, run.length * 2, radius * (layer.width ?? 1), 6, false);
          const mesh = new THREE.Mesh(tube, material);
          mesh.castShadow = true;
          group.add(mesh);
        }
        run = [];
      };
      for (let i = 0; i + 1 < path.length; i++) {
        const [u0, v0] = path[i], [u1, v1] = path[i + 1];
        const n = Math.max(1, Math.ceil(Math.hypot(u1 - u0, v1 - v0) / step));
        for (let k = (i === 0 ? 0 : 1); k <= n; k++) {
          const u = u0 + (u1 - u0) * k / n, v = v0 + (v1 - v0) * k / n;
          const z = heightAt(u, v);
          if (Number.isNaN(z) || u < 0 || u > 1 || v < 0 || v > 1) { flush(); continue; }
          run.push(new THREE.Vector3((u - 0.5) * scene.widthM, (v - 0.5) * scene.heightM, z * settings.exaggeration + lift));
        }
      }
      flush();
    }
  }
}

// --- light ----------------------------------------------------------------

const sun = new THREE.DirectionalLight(0xffffff, 2.6);
sun.castShadow = true;
sun.shadow.mapSize.set(4096, 4096);
sun.shadow.bias = -0.0004;
sun.shadow.normalBias = 0.02;
world.add(sun);
world.add(sun.target);
const sky = new THREE.HemisphereLight(0xdfe8ff, 0x3a3128, settings.ambient);
world.add(sky);

const extent = Math.max(scene.widthM, scene.heightM);

function placeSun() {
  const az = THREE.MathUtils.degToRad(settings.sunAzimuth);
  const el = THREE.MathUtils.degToRad(settings.sunElevation);
  // azimuth clockwise from north (+y), toward east (+x)
  const dir = new THREE.Vector3(Math.sin(az) * Math.cos(el), Math.cos(az) * Math.cos(el), Math.sin(el));
  sun.position.copy(dir.multiplyScalar(extent * 2));
  const box = extent * 0.75;
  Object.assign(sun.shadow.camera, { left: -box, right: box, top: box, bottom: -box, near: 1, far: extent * 5 });
  sun.shadow.camera.updateProjectionMatrix();
}

let builtSides = "", builtLines = NaN, builtSmooth = settings.edges !== "stepped";
function apply() {
  terrain.scale.z = settings.exaggeration;
  if (settings.exaggeration !== builtLines) { builtLines = settings.exaggeration; buildLines(); }
  const smooth = settings.edges !== "stepped";
  if (smooth !== builtSmooth) {
    builtSmooth = smooth;
    outlineEdges = outline(smooth);
    buildIndices(smooth);
    relaxOutline(outlineEdges, smooth);
    geometry.setIndex(indices);
    geometry.attributes.position.needsUpdate = true;
    geometry.computeVertexNormals();
  }
  const sideKey = [settings.sides, settings.baseDepth, smooth].join();
  if (sideKey !== builtSides) { builtSides = sideKey; buildSides(); }
  sideMaterial.color.set(settings.sideColor);
  // a little of its own light: walls facing away from the sun stay readable
  sideMaterial.emissive.set(settings.sideColor).multiplyScalar(0.25);
  renderer.shadowMap.enabled = settings.shadows;
  sun.castShadow = settings.shadows;
  material.needsUpdate = true;
  sky.intensity = settings.ambient;
  renderer.setClearColor(new THREE.Color(settings.background), 1);
  placeSun();
}

// --- camera -----------------------------------------------------------------

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.12;
controls.maxPolarAngle = Math.PI * 0.495; // never below the horizon
controls.screenSpacePanning = true;

function home() {
  // from the south, looking north and down at 40°
  const distance = extent * 1.35;
  const tilt = THREE.MathUtils.degToRad(40);
  camera.position.set(0, -distance * Math.cos(tilt), distance * Math.sin(tilt));
  controls.target.set(0, 0, 0);
  controls.update();
}

function resize() {
  const w = container.clientWidth, h = container.clientHeight;
  renderer.setSize(w, h);
  camera.aspect = w / Math.max(h, 1);
  camera.updateProjectionMatrix();
}
window.addEventListener("resize", resize);

// --- annotations: north arrow, scale bar, color bar, exaggeration -----------------

const annotations = document.createElement("canvas");
annotations.style.cssText = "position:absolute;inset:0;width:100%;height:100%;pointer-events:none";
container.appendChild(annotations);

function niceLength(meters) {
  const power = 10 ** Math.floor(Math.log10(meters));
  for (const m of [5, 2, 1]) if (m * power <= meters) return m * power;
  return power;
}
function lengthLabel(meters) {
  return meters >= 1000 ? `${+(meters / 1000).toPrecision(3)} km` : `${+meters.toPrecision(3)} m`;
}
function inkColor() {
  // dark ink on a light background, light ink otherwise
  const c = new THREE.Color(settings.background);
  return 0.299 * c.r + 0.587 * c.g + 0.114 * c.b > 0.6 ? "#1b1b1b" : "#f2f2f2";
}

// Draw them on a 2D context the size of the view (or of a still); ``k``
// scales them, so a still looks like the view at any size
function drawAnnotations(ctx, w, h, k) {
  ctx.clearRect(0, 0, w, h);
  const ink = inkColor(), margin = 20 * k;
  ctx.font = `${13 * k}px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif`;
  ctx.fillStyle = ink;
  ctx.strokeStyle = ink;
  ctx.lineWidth = 1.5 * k;
  const target = controls.target;
  const toScreen = (v) => {
    const p = v.clone().project(camera);
    return [(p.x + 1) / 2 * w, (1 - p.y) / 2 * h];
  };
  if (settings.scaleBar) {
    // ground distance across the screen at the orbit target
    const right = new THREE.Vector3().setFromMatrixColumn(camera.matrixWorld, 0).setZ(0).normalize();
    const [x0] = toScreen(target), [x1] = toScreen(target.clone().addScaledVector(right, extent * 0.1));
    const pixelsPerMeter = Math.abs(x1 - x0) / (extent * 0.1);
    if (pixelsPerMeter > 0 && Number.isFinite(pixelsPerMeter)) {
      const meters = niceLength((w * 0.16) / pixelsPerMeter);
      const bar = meters * pixelsPerMeter, barH = 6 * k;
      const right_ = w - margin, bottom = h - margin;
      ctx.fillRect(right_ - bar, bottom - barH, bar / 2, barH);
      ctx.strokeRect(right_ - bar, bottom - barH, bar, barH);
      ctx.textAlign = "right";
      ctx.fillText(lengthLabel(meters), right_, bottom - barH - 6 * k);
      if (settings.exaggeration !== 1) {
        ctx.fillText(`Vertical exaggeration ${+settings.exaggeration.toFixed(2)}×`, right_, bottom - barH - 24 * k);
      }
    }
  } else if (settings.exaggeration !== 1) {
    ctx.textAlign = "right";
    ctx.fillText(`Vertical exaggeration ${+settings.exaggeration.toFixed(2)}×`, w - margin, h - margin);
  }
  if (settings.northArrow) {
    // which way north (+y) points on screen at the target
    const [ax, ay] = toScreen(target), [bx, by] = toScreen(target.clone().add(new THREE.Vector3(0, extent * 0.05, 0)));
    const angle = Math.atan2(bx - ax, -(by - ay));
    const cx = margin + 18 * k, cy = h - margin - 26 * k, r = 16 * k;
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle);
    ctx.beginPath();
    ctx.moveTo(0, -r); ctx.lineTo(r * 0.55, r * 0.7); ctx.lineTo(0, r * 0.35); ctx.lineTo(-r * 0.55, r * 0.7);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
    ctx.textAlign = "center";
    const lx = cx + Math.sin(angle) * (r + 10 * k), ly = cy - Math.cos(angle) * (r + 10 * k);
    ctx.fillText("N", lx, ly + 5 * k);
  }
  const legend = scene.legend;
  if (settings.colorBar && legend) {
    const barW = 14 * k, barH = Math.min(h * 0.35, 220 * k);
    const x = w - margin - barW, y = margin + 18 * k;
    const gradient = ctx.createLinearGradient(0, y + barH, 0, y);
    legend.colors.forEach((color, i) => gradient.addColorStop(i / (legend.colors.length - 1), color));
    ctx.fillStyle = gradient;
    ctx.fillRect(x, y, barW, barH);
    ctx.strokeRect(x, y, barW, barH);
    ctx.fillStyle = ink;
    ctx.textAlign = "right";
    ctx.fillText(legend.label, x + barW, y - 8 * k);
    ctx.fillText(`${Math.round(legend.high)}`, x - 6 * k, y + 10 * k);
    ctx.fillText(`${Math.round(legend.low)}`, x - 6 * k, y + barH);
  }
}

function drawViewAnnotations() {
  const ratio = window.devicePixelRatio || 1;
  const w = Math.round(container.clientWidth * ratio), h = Math.round(container.clientHeight * ratio);
  if (annotations.width !== w || annotations.height !== h) { annotations.width = w; annotations.height = h; }
  drawAnnotations(annotations.getContext("2d"), w, h, ratio);
}

function frame() {
  controls.update();
  renderer.render(world, camera);
  drawViewAnnotations();
  requestAnimationFrame(frame);
}

// --- what Varda (and the page's own controls) call ---------------------------------

window.viewer = {
  ready: false,
  set(changes) {
    Object.assign(settings, changes);
    apply();
    syncPanel();
  },
  settings() {
    return Object.assign({}, settings);
  },
  getCamera() {
    return { position: camera.position.toArray(), target: controls.target.toArray(), fov: camera.fov };
  },
  setCamera(view) {
    camera.position.fromArray(view.position);
    controls.target.fromArray(view.target);
    if (view.fov) { camera.fov = view.fov; camera.updateProjectionMatrix(); }
    controls.update();
  },
  home,
  // A flyover: the camera circles the target; orbitStill renders the frame
  // ``degrees`` round from where it was at orbitBegin
  orbitBegin() {
    this._orbit = { position: camera.position.clone(), target: controls.target.clone() };
  },
  orbitStill(degrees, width, height) {
    const { position, target } = this._orbit;
    const offset = position.clone().sub(target).applyAxisAngle(new THREE.Vector3(0, 0, 1), THREE.MathUtils.degToRad(degrees));
    camera.position.copy(target).add(offset);
    controls.target.copy(target);
    camera.lookAt(target);
    return this.still(width, height, false);
  },
  orbitEnd() {
    if (!this._orbit) return;
    camera.position.copy(this._orbit.position);
    controls.target.copy(this._orbit.target);
    controls.update();
    this._orbit = null;
  },
  setLines(index, changes) {
    const layer = lineLayers[index];
    if (layer && "visible" in changes) layer.group.visible = changes.visible;
  },
  setOverlay(index, changes) {
    const overlay = overlays[index];
    if (!overlay) return;
    if ("opacity" in changes) overlay.layer.opacity = changes.opacity;
    if ("visible" in changes) overlay.mesh.visible = changes.visible;
  },
  // A still at any size (within the GPU's limits), as a PNG data URL
  still(width, height, transparent) {
    const size = new THREE.Vector2();
    renderer.getSize(size);
    const ratio = renderer.getPixelRatio();
    renderer.setPixelRatio(1);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    if (transparent) renderer.setClearColor(0x000000, 0);
    renderer.render(world, camera);
    // the frame and its annotations, scaled as they look in the view
    const still = document.createElement("canvas");
    still.width = width;
    still.height = height;
    const ctx = still.getContext("2d");
    ctx.drawImage(renderer.domElement, 0, 0);
    const k = width / Math.max(container.clientWidth, 1);
    const overlay = document.createElement("canvas");
    overlay.width = width;
    overlay.height = height;
    drawAnnotations(overlay.getContext("2d"), width, height, k);
    ctx.drawImage(overlay, 0, 0);
    const url = still.toDataURL("image/png");
    renderer.setClearColor(new THREE.Color(settings.background), 1);
    renderer.setPixelRatio(ratio);
    renderer.setSize(size.x, size.y);
    resize();
    renderer.render(world, camera);
    return url;
  },
  info() {
    const gl = renderer.getContext();
    return { maxTexture: gl.getParameter(gl.MAX_TEXTURE_SIZE), triangles: indices.length / 3, zLow, zHigh };
  },
};

// --- the page's own controls (in exported pages) -------------------------------------

const panel = document.getElementById("panel");
function syncPanel() {
  if (!panel) return;
  for (const input of panel.querySelectorAll("input[data-setting]")) {
    const value = settings[input.dataset.setting];
    if (input.type === "checkbox") input.checked = value;
    else input.value = value;
  }
}
if (panel) {
  for (const input of panel.querySelectorAll("input[data-setting]")) {
    input.addEventListener("input", () => {
      const value = input.type === "checkbox" ? input.checked : parseFloat(input.value);
      window.viewer.set({ [input.dataset.setting]: value });
    });
  }
  const homeButton = document.getElementById("home");
  if (homeButton) homeButton.addEventListener("click", home);
}

resize();
apply();
if (scene.camera) window.viewer.setCamera(scene.camera);
else home();
syncPanel();
textureReady.then(() => {
  window.viewer.ready = true;
  frame();
  console.log("varda:ready");
});
