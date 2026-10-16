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
// two triangles per cell, leaving out cells that touch no-data
const indices = [];
for (let r = 0; r < rows - 1; r++) {
  for (let c = 0; c < cols - 1; c++) {
    const a = r * cols + c, b = a + 1, d = a + cols, e = d + 1;
    if (quantized[a] && quantized[b] && quantized[d] && quantized[e]) {
      indices.push(a, d, b, b, d, e);
    }
  }
}
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

const textureReady = new Promise((resolve) => {
  if (!scene.texture) { material.color.set("#b8b0a4"); resolve(); return; }
  new THREE.TextureLoader().load(scene.texture, (texture) => {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
    material.map = texture;
    material.needsUpdate = true;
    resolve();
  });
});

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

function apply() {
  terrain.scale.z = settings.exaggeration;
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

function frame() {
  controls.update();
  renderer.render(world, camera);
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
    const url = renderer.domElement.toDataURL("image/png");
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
