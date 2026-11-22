/*
 * 3B Dijital İkiz — Sandvik LH517i benzeri yükleyici (LHD) ve TH551i benzeri kamyon
 * ─────────────────────────────────────────────────────────────────
 * Model tamamen koddan üretilir (dış model/marka/logo yok); ölçüler üretici
 * verisine yakındır. Yükleyici ~11,8 m × 3,1 m, kamyon ~10,4 m × 3,3 m.
 * Sahne stüdyo zeminidir (siyah fon, düz zemin) — araç stantta sergilenir gibi.
 *
 *   Twin3D.supported()                 → WebGL var mı
 *   Twin3D.mount(el, tip)              → sahneyi kur (tip: "loader" | "truck")
 *   Twin3D.update(okuma)               → canlı veri (hız, faz, sensör etiketleri)
 *   Twin3D.focus(bilesen, bilgi)       → kamerayı bileşene götür, vurgula
 *   Twin3D.clearFocus()                → genel görünüme dön
 *   Twin3D.unmount()                   → GPU kaynaklarını bırak
 *
 * Vurgulanan bileşen, modelin tahmininden gelir (RUL bileşen olasılıkları ya da
 * sensör artıkları) — simülatörün gizli "gerçek" bilgisinden değil.
 */
import * as THREE from 'three';
import { OrbitControls } from './vendor/three/OrbitControls.js';
import { RoomEnvironment } from './vendor/three/RoomEnvironment.js';
import { RoundedBoxGeometry } from './vendor/three/RoundedBoxGeometry.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);

// ── Bileşen kataloğu: kamera pozu, odak noktası, iç parça mı (kaput saydamlaşır)
const COMP_LOADER = {
  rulman:         { ad: 'Rulman aşınması',            yer: 'Ön aks — tekerlek göbeği',  cam: V(5.6, 1.5, 5.2),  tgt: V(2.5, 1.0, 1.2),  ic: false },
  fren:           { ad: 'Fren sürtmesi / ısınma',      yer: 'Arka aks — ıslak disk fren', cam: V(0.6, 1.4, 5.0),  tgt: V(-1.9, 1.0, 1.2), ic: false },
  hidrolik_pompa: { ad: 'Hidrolik pompa arızası',      yer: 'Hidrolik sistem — pompa',    cam: V(-1.3, 1.35, 5.0), tgt: V(-0.15, 0.95, 0.84), ic: false },
  transmisyon:    { ad: 'Transmisyon arızası',         yer: 'Güç aktarma — şanzıman',     cam: V(-0.75, 0.65, 4.5), tgt: V(-0.8, 0.9, 0.0), ic: false },
  motor_isi:      { ad: 'Motor aşırı ısınması',        yer: 'Motor bloğu',                cam: V(-2.0, 4.4, 5.4), tgt: V(-3.7, 1.8, 0.0), ic: true  },
  enjektor:       { ad: 'Enjektör / yanma arızası',    yer: 'Motor — enjektör hattı',     cam: V(-2.6, 4.6, 3.4), tgt: V(-3.7, 2.15, 0.0), ic: true },
  motor_sargi:    { ad: 'Tahrik motoru sargı arızası', yer: 'Tahrik motoru / alternatör', cam: V(-1.2, 2.8, 4.4), tgt: V(-2.75, 1.65, 0.55), ic: true },
  sogutma:        { ad: 'Soğutma sistemi arızası',     yer: 'Radyatör / fan',             cam: V(-9.6, 2.4, 3.8), tgt: V(-5.3, 1.7, 0.0), ic: false },
};
const HOME_LOADER = { cam: V(5.8, 3.3, 12.6), tgt: V(-0.3, 1.25, 0) };

// Kamyon: kabin sağda (+z), motor solda (−z) — motor odakları sol taraftan bakar
const COMP_TRUCK = {
  rulman:         { ad: 'Rulman aşınması',            yer: 'Ön aks — tekerlek göbeği',  cam: V(6.4, 1.6, 5.6),  tgt: V(3.3, 1.06, 1.3),  ic: false },
  fren:           { ad: 'Fren sürtmesi / ısınma',      yer: 'Arka aks — ıslak disk fren', cam: V(0.6, 1.5, 5.4),  tgt: V(-2.3, 1.06, 1.3), ic: false },
  hidrolik_pompa: { ad: 'Hidrolik pompa arızası',      yer: 'Damper hidroliği — pompa',   cam: V(-0.6, 1.3, 5.0), tgt: V(-0.1, 1.0, 0.86), ic: false },
  transmisyon:    { ad: 'Transmisyon arızası',         yer: 'Güç aktarma — şanzıman',     cam: V(0.9, 0.8, 4.8),  tgt: V(0.75, 1.0, 0.0), ic: false },
  motor_isi:      { ad: 'Motor aşırı ısınması',        yer: 'Motor bloğu',                cam: V(6.0, 4.4, -4.8), tgt: V(3.5, 1.95, -0.78), ic: true },
  enjektor:       { ad: 'Enjektör / yanma arızası',    yer: 'Motor — enjektör hattı',     cam: V(4.9, 4.7, -3.6), tgt: V(3.6, 2.5, -0.72), ic: true },
  motor_sargi:    { ad: 'Tahrik motoru sargı arızası', yer: 'Tahrik motoru / alternatör', cam: V(6.6, 3.0, -3.4), tgt: V(4.45, 1.7, -0.3), ic: true },
  sogutma:        { ad: 'Soğutma sistemi arızası',     yer: 'Radyatör / fan',             cam: V(9.6, 2.4, -3.4), tgt: V(5.0, 2.0, -0.78), ic: false },
};
const HOME_TRUCK = { cam: V(7.4, 3.8, 13.2), tgt: V(0.2, 1.7, 0) };

// ── Faz → bom / kepçe açısı (radyan): canlı fazı fiziksel harekete çevirir
const POSE = {
  idle:            [0.00, 0.10], approach_pile:  [-0.04, 0.02],
  picking_up:      [0.10, 0.42], hauling_loaded: [0.16, 0.55],
  approach_dump:   [0.50, 0.50], dumping:        [0.62, -0.62],
  returning_empty: [0.05, 0.18], kotu_yol:       [0.16, 0.55],
};
const LOADED = new Set(['picking_up', 'hauling_loaded', 'approach_dump', 'kotu_yol',
  'getting_loaded', 'accelerating_loaded', 'climbing_loaded', 'arriving_dump']);

let S = null;   // aktif sahne durumu

export function supported() {
  try {
    const c = document.createElement('canvas');
    return !!(window.WebGLRenderingContext && (c.getContext('webgl2') || c.getContext('webgl')));
  } catch (e) { return false; }
}

// ─────────────────────────────────────────────────────────────────
// Malzemeler ve dokular
// ─────────────────────────────────────────────────────────────────
function noiseTexture(size, base, spread, seed = 1, repeat = 1) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  const img = g.createImageData(size, size);
  let s = seed;
  const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < size * size; i++) {
    const n = (rnd() - 0.5) * spread;
    img.data[i * 4] = base[0] + n; img.data[i * 4 + 1] = base[1] + n;
    img.data[i * 4 + 2] = base[2] + n; img.data[i * 4 + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  // yumuşak lekeler
  for (let k = 0; k < size / 3; k++) {
    const v = rnd() < 0.55 ? 0 : 255;
    g.fillStyle = `rgba(${v},${v},${v},${0.03 + rnd() * 0.05})`;
    g.beginPath(); g.arc(rnd() * size, rnd() * size, 4 + rnd() * size / 10, 0, 7); g.fill();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat, repeat);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 4;
  return t;
}

// Stüdyo zemini: ortası hafif açık gri, kenarlara doğru siyaha erir (fon ile birleşir)
function floorTexture() {
  const c = document.createElement('canvas');
  c.width = c.height = 512;
  const g = c.getContext('2d');
  const gr = g.createRadialGradient(256, 256, 0, 256, 256, 256);
  gr.addColorStop(0, '#ffffff'); gr.addColorStop(0.35, '#b0b0b0'); gr.addColorStop(0.75, '#202020'); gr.addColorStop(1, '#000000');
  g.fillStyle = gr; g.fillRect(0, 0, 512, 512);
  return new THREE.CanvasTexture(c);      // alfa maskesi: zemin kenarda tamamen saydam
}

function hazardTexture() {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 64;
  const g = c.getContext('2d');
  g.fillStyle = '#e0b000'; g.fillRect(0, 0, 256, 64);
  g.fillStyle = '#151515';
  for (let x = -64; x < 320; x += 48) {
    g.beginPath(); g.moveTo(x, 64); g.lineTo(x + 24, 64); g.lineTo(x + 88, 0); g.lineTo(x + 64, 0); g.fill();
  }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function makeMaterials() {
  const std = (o) => new THREE.MeshStandardMaterial(o);
  return {
    paint:    std({ color: 0xd2501c, metalness: 0.25, roughness: 0.42 }),
    paintWorn:std({ color: 0xb8461a, metalness: 0.3, roughness: 0.62 }),
    hood:     std({ color: 0xd2501c, metalness: 0.25, roughness: 0.42, transparent: true, opacity: 1 }),
    cab:      std({ color: 0xe9e9e4, metalness: 0.15, roughness: 0.38 }),
    glass:    std({ color: 0x1a2731, metalness: 0.85, roughness: 0.04, envMapIntensity: 2.4 }),
    frame:    std({ color: 0x1e1f21, metalness: 0.45, roughness: 0.6 }),
    rubber:   std({ color: 0x151515, metalness: 0.0, roughness: 0.93 }),
    rim:      std({ color: 0x26282b, metalness: 0.65, roughness: 0.42 }),
    steel:    std({ color: 0x5c6066, metalness: 0.8, roughness: 0.38 }),
    chrome:   std({ color: 0xe4e6e8, metalness: 1.0, roughness: 0.12 }),
    engine:   std({ color: 0x3a3d42, metalness: 0.6, roughness: 0.5 }),
    yellow:   std({ color: 0xe2b400, metalness: 0.2, roughness: 0.45 }),
    hazard:   std({ map: hazardTexture(), metalness: 0.2, roughness: 0.5 }),
    lamp:     std({ color: 0xffffff, emissive: 0xfff6e0, emissiveIntensity: 3.0, roughness: 0.2 }),
    lampRed:  std({ color: 0x550000, emissive: 0xff2010, emissiveIntensity: 1.6 }),
    beacon:   std({ color: 0x663300, emissive: 0xff9a00, emissiveIntensity: 1.8 }),
    hose:     std({ color: 0x101010, metalness: 0.1, roughness: 0.7 }),
    grille:   std({ color: 0x0c0c0d, metalness: 0.5, roughness: 0.55 }),
    rock:     std({ map: noiseTexture(256, [96, 90, 84], 30, 7, 2), roughness: 0.96, metalness: 0.02 }),
    floor:    std({ color: 0x2b2d31, alphaMap: floorTexture(), transparent: true, depthWrite: false,
                    roughness: 0.78, metalness: 0.0 }),
  };
}

// ─────────────────────────────────────────────────────────────────
// Geometri yardımcıları
// ─────────────────────────────────────────────────────────────────
function mesh(geo, mat, parent, pos, rot) {
  const m = new THREE.Mesh(geo, mat);
  if (pos) m.position.copy(pos);
  if (rot) m.rotation.set(rot[0], rot[1], rot[2]);
  m.castShadow = true; m.receiveShadow = true;
  if (parent) parent.add(m);
  return m;
}
const rbox = (w, h, d, r = 0.06, seg = 3) => new RoundedBoxGeometry(w, h, d, seg, Math.min(r, w / 2, h / 2, d / 2) * 0.999);
const cylZ = (r1, r2, len, seg = 32) => new THREE.CylinderGeometry(r1, r2, len, seg).rotateX(Math.PI / 2);
const cylX = (r1, r2, len, seg = 24) => new THREE.CylinderGeometry(r1, r2, len, seg).rotateZ(Math.PI / 2);

/** x-y profilinden (açık eğri) kalınlıklı kabuk üretir, z boyunca extrude eder. */
function shellFromProfile(pts, thick, depth) {
  const n = pts.length, inner = [];
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
    const dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy) || 1;
    inner.push(new THREE.Vector2(pts[i].x - dy / L * thick, pts[i].y + dx / L * thick));
  }
  const shape = new THREE.Shape([...pts, ...inner.reverse()]);
  const g = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false, curveSegments: 8 });
  g.translate(0, 0, -depth / 2);
  return g;
}

function plateFromOutline(pts, depth) {
  const g = new THREE.ExtrudeGeometry(new THREE.Shape(pts), { depth, bevelEnabled: true,
    bevelThickness: 0.015, bevelSize: 0.015, bevelSegments: 2, curveSegments: 8 });
  g.translate(0, 0, -depth / 2);
  return g;
}

function arcPlate(rIn, rOut, a0, a1, depth) {
  const s = new THREE.Shape();
  s.absarc(0, 0, rOut, a0, a1, false);
  s.absarc(0, 0, rIn, a1, a0, true);
  const g = new THREE.ExtrudeGeometry(s, { depth, bevelEnabled: true, bevelThickness: 0.02,
    bevelSize: 0.02, bevelSegments: 2, curveSegments: 40 });
  g.translate(0, 0, -depth / 2);
  return g;
}

// ─────────────────────────────────────────────────────────────────
// Tekerlek (lastik + diş + jant + göbek)
// ─────────────────────────────────────────────────────────────────
function buildWheel(M, side) {
  const w = new THREE.Group();
  const prof = [[0.62, -0.36], [0.78, -0.385], [0.89, -0.37], [0.95, -0.32], [0.975, -0.22],
    [0.98, 0], [0.975, 0.22], [0.95, 0.32], [0.89, 0.37], [0.78, 0.385], [0.62, 0.36]]
    .map(([r, y]) => new THREE.Vector2(r, y));
  const tire = new THREE.LatheGeometry(prof, 64).rotateX(Math.PI / 2);
  mesh(tire, M.rubber, w);
  // diş blokları (chevron)
  const lug = new THREE.BoxGeometry(0.15, 0.07, 0.30);
  const N = 28, inst = new THREE.InstancedMesh(lug, M.rubber, N * 2);
  const q = new THREE.Object3D();
  for (let i = 0; i < N * 2; i++) {
    const half = i % 2, th = (Math.floor(i / 2) + half * 0.5) / N * Math.PI * 2;
    q.position.set(Math.cos(th) * 0.995, Math.sin(th) * 0.995, half ? 0.17 : -0.17);
    q.rotation.set(0, 0, th);
    q.rotateX(half ? 0.38 : -0.38);
    q.updateMatrix(); inst.setMatrixAt(i, q.matrix);
  }
  inst.castShadow = true; w.add(inst);
  // jant
  mesh(cylZ(0.6, 0.6, 0.66, 40), M.rim, w);
  const dish = new THREE.LatheGeometry([[0.0, 0.0], [0.22, 0.0], [0.30, -0.05], [0.52, -0.1], [0.6, -0.04]]
    .map(([r, y]) => new THREE.Vector2(r, y)), 40).rotateX(-Math.PI / 2);
  mesh(dish, M.rim, w, V(0, 0, 0.3 * side));
  if (side < 0) w.children[w.children.length - 1].scale.z = -1;
  const hub = mesh(cylZ(0.24, 0.27, 0.18, 32), M.steel, w, V(0, 0, 0.36 * side));
  hub.name = 'hub';
  const bolt = new THREE.InstancedMesh(cylZ(0.025, 0.025, 0.06, 8), M.chrome, 12);
  for (let i = 0; i < 12; i++) {
    const th = i / 12 * Math.PI * 2;
    q.position.set(Math.cos(th) * 0.36, Math.sin(th) * 0.36, 0.33 * side);
    q.rotation.set(0, 0, 0); q.updateMatrix(); bolt.setMatrixAt(i, q.matrix);
  }
  w.add(bolt);
  return w;
}

// ─────────────────────────────────────────────────────────────────
// Yükleyici modeli
// ─────────────────────────────────────────────────────────────────
function buildLoader(M) {
  const root = new THREE.Group();
  const parts = {};               // bileşen → vurgulanacak meshler
  const add = (k, m) => { (parts[k] = parts[k] || []).push(m); return m; };
  const AX_F = 2.5, AX_R = -1.9, WY = 0.98, WZ = 1.15;

  // ── Tekerlekler + çamurluklar
  const wheels = [];
  for (const [x, z] of [[AX_F, WZ], [AX_F, -WZ], [AX_R, WZ], [AX_R, -WZ]]) {
    const w = buildWheel(M, Math.sign(z));
    w.position.set(x, WY, z);
    root.add(w); wheels.push(w);
    const hub = w.getObjectByName('hub');
    add(x > 0 ? 'rulman' : 'fren', hub);
    mesh(arcPlate(1.06, 1.14, 0.25, Math.PI - 0.25, 0.84), M.paint, root, V(x, WY, z));
  }

  // ── Akslar, diferansiyel, şaftlar
  for (const x of [AX_F, AX_R]) {
    const ax = mesh(cylZ(0.2, 0.2, 2.0, 24), M.frame, root, V(x, WY, 0));
    const diff = mesh(new THREE.SphereGeometry(0.36, 24, 16), M.frame, root, V(x, WY, 0));
    for (const z of [0.78, -0.78]) {
      const ring = mesh(cylZ(0.34, 0.3, 0.2, 28), M.steel, root, V(x, WY, z));
      add(x > 0 ? 'rulman' : 'fren', ring);
    }
    add(x > 0 ? 'rulman' : 'fren', ax); add(x > 0 ? 'rulman' : 'fren', diff);
  }
  const shaftF = mesh(cylX(0.07, 0.07, 3.0, 16), M.steel, root, V(1.0, 0.8, 0));
  shaftF.rotation.z = Math.atan2(WY - 0.8, AX_F - (-0.5)) * 0.3;
  const shaftR = mesh(cylX(0.07, 0.07, 0.8, 16), M.steel, root, V(-1.55, 0.86, 0));
  add('transmisyon', shaftF); add('transmisyon', shaftR);

  // ── Ön şasi (kepçe tarafı)
  mesh(rbox(2.9, 0.95, 1.2, 0.08), M.paint, root, V(2.1, 1.35, 0));
  mesh(rbox(1.0, 0.5, 1.25, 0.08), M.paint, root, V(3.25, 1.9, 0));            // burun
  for (const z of [0.45, -0.45]) {                                              // ön farlar
    mesh(rbox(0.22, 0.2, 0.28, 0.03), M.frame, root, V(3.62, 2.1, z));
    mesh(new THREE.CircleGeometry(0.075, 20).rotateY(Math.PI / 2), M.lamp, root, V(3.735, 2.1, z));
  }

  // ── Mafsal (articulation)
  mesh(rbox(0.7, 0.85, 1.0, 0.06), M.frame, root, V(0.55, 1.2, 0));
  for (const y of [0.7, 1.7]) mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.25, 20), M.chrome, root, V(0.55, y, 0));
  for (const z of [0.5, -0.5]) {                                                // direksiyon silindirleri
    const c = mesh(cylX(0.06, 0.06, 1.1, 14), M.chrome, root, V(0.6, 1.05, z));
    c.rotation.y = z > 0 ? 0.25 : -0.25;
  }

  // ── Arka şasi
  for (const z of [0.55, -0.55]) mesh(rbox(5.6, 0.5, 0.18, 0.04), M.paint, root, V(-2.45, 1.0, z));
  mesh(rbox(1.1, 0.35, 1.3, 0.04), M.frame, root, V(-0.35, 1.38, 0));

  // ── Şanzıman + hidrolik pompa (PTO üzerinde) + hortumlar
  const trans = mesh(rbox(1.0, 0.6, 0.8, 0.07), M.steel, root, V(-0.8, 0.9, 0));
  const tconv = mesh(cylX(0.32, 0.32, 0.35, 28), M.steel, root, V(-1.45, 0.95, 0));
  add('transmisyon', trans); add('transmisyon', tconv);
  const pump = mesh(cylX(0.2, 0.2, 0.5, 24), M.engine, root, V(0.0, 0.95, 0.84));
  const pumpBody = mesh(rbox(0.32, 0.3, 0.3, 0.04), M.engine, root, V(-0.32, 0.95, 0.84));
  add('hidrolik_pompa', pump); add('hidrolik_pompa', pumpBody);
  const hoses = [];
  for (const [i, pts] of [
    [V(0.1, 1.05, 0.62), V(0.6, 1.4, 0.55), V(1.4, 1.75, 0.5), V(2.2, 2.05, 0.4)],
    [V(-0.3, 1.1, 0.62), V(-0.1, 1.55, 0.7), V(0.2, 1.85, -0.2), V(0.1, 1.9, -0.7)],
    [V(0.05, 0.85, 0.7), V(0.7, 0.95, 0.75), V(1.6, 1.25, 0.62), V(2.6, 1.55, 0.55)],
  ].entries()) {
    const curve = new THREE.CatmullRomCurve3(pts);
    const h = mesh(new THREE.TubeGeometry(curve, 40, i === 1 ? 0.045 : 0.035, 10), M.hose, root);
    add('hidrolik_pompa', h); hoses.push(h);
  }

  // ── Hidrolik tank (kabinin karşı tarafı)
  mesh(rbox(1.3, 0.95, 0.9, 0.08), M.paint, root, V(-0.25, 1.95, -0.72));
  mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.08, 16), M.frame, root, V(-0.1, 2.46, -0.72));

  // ── Kabin (beyaz, sağ tarafta, mafsalın hemen arkasında)
  const cab = new THREE.Group(); cab.position.set(-0.35, 0, 0.78); root.add(cab);
  mesh(rbox(1.45, 1.35, 1.2, 0.1), M.cab, cab, V(0, 2.12, 0));
  mesh(rbox(1.55, 0.12, 1.3, 0.05), M.cab, cab, V(0, 2.86, 0));                 // tavan
  mesh(rbox(0.04, 0.72, 0.95, 0.02), M.glass, cab, V(0.73, 2.3, 0));           // ön cam
  mesh(rbox(0.04, 0.72, 0.95, 0.02), M.glass, cab, V(-0.73, 2.3, 0));          // arka cam
  mesh(rbox(1.15, 0.72, 0.04, 0.02), M.glass, cab, V(0.02, 2.3, 0.61));        // yan cam
  mesh(rbox(1.2, 0.12, 0.05, 0.02), M.frame, cab, V(0.0, 1.85, 0.615));
  for (const z of [-0.35, 0.35]) {                                              // tavan farları
    mesh(rbox(0.16, 0.14, 0.24, 0.03), M.frame, cab, V(0.72, 2.98, z));
    mesh(new THREE.CircleGeometry(0.06, 16).rotateY(Math.PI / 2), M.lamp, cab, V(0.805, 2.98, z));
  }
  mesh(new THREE.CylinderGeometry(0.07, 0.08, 0.12, 16), M.beacon, cab, V(-0.5, 2.98, 0));
  // merdiven + korkuluk (sarı)
  const lad = new THREE.Group(); lad.position.set(0.45, 0, 0.67); cab.add(lad);
  for (const dx of [-0.2, 0.2]) mesh(cylX(0.022, 0.022, 0.9, 8).rotateZ(Math.PI / 2), M.yellow, lad, V(dx, 1.0, 0));
  for (const y of [0.65, 0.95, 1.25]) mesh(new THREE.BoxGeometry(0.42, 0.04, 0.14), M.yellow, lad, V(0, y, 0));

  // ── Motor bölmesi (kaput saydamlaşabilir) + iç parçalar
  const hood = new THREE.Group(); root.add(hood);
  const hoodMain = mesh(rbox(2.95, 1.05, 2.3, 0.14), M.hood, hood, V(-3.85, 1.85, 0));
  const vent = new THREE.InstancedMesh(new THREE.BoxGeometry(0.06, 0.03, 1.2), M.grille, 14);
  const q = new THREE.Object3D();
  for (let i = 0; i < 14; i++) { q.position.set(-4.9 + i * 0.12, 2.385, 0); q.updateMatrix(); vent.setMatrixAt(i, q.matrix); }
  hood.add(vent);
  for (const z of [1.08, -1.08]) mesh(cylX(0.025, 0.025, 2.6, 8), M.yellow, hood, V(-3.85, 2.48, z));
  for (const x of [-2.6, -5.1]) for (const z of [1.08, -1.08])
    mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.12, 8), M.yellow, hood, V(x, 2.43, z));
  const exhaust = mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.45, 16), M.frame, hood, V(-3.0, 2.55, -0.6));
  const engine = new THREE.Group(); root.add(engine);
  const block = mesh(rbox(1.9, 0.75, 1.0, 0.06), M.engine, engine, V(-3.7, 1.75, 0));
  const head = mesh(rbox(1.7, 0.18, 0.7, 0.04), M.steel, engine, V(-3.7, 2.2, 0));
  add('motor_isi', block); add('motor_isi', head);
  for (let i = 0; i < 6; i++) {
    const inj = mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.16, 12), M.chrome, engine, V(-4.4 + i * 0.28, 2.37, 0.12));
    add('enjektor', inj);
  }
  add('enjektor', mesh(cylX(0.03, 0.03, 1.6, 8), M.steel, engine, V(-3.7, 2.42, 0.22)));
  const alt = mesh(cylX(0.2, 0.2, 0.45, 24), M.steel, engine, V(-2.75, 1.65, 0.55));
  add('motor_sargi', alt);
  add('motor_sargi', mesh(new THREE.TorusGeometry(0.2, 0.025, 8, 24).rotateY(Math.PI / 2), M.chrome, engine, V(-2.5, 1.65, 0.55)));

  // ── Arka: radyatör ızgarası, karşı ağırlık, stoplar, uyarı şeridi
  const radFrame = mesh(rbox(0.16, 1.0, 1.9, 0.04), M.paint, root, V(-5.34, 1.85, 0));
  const grill = new THREE.InstancedMesh(new THREE.BoxGeometry(0.04, 0.035, 1.6), M.grille, 11);
  for (let i = 0; i < 11; i++) { q.position.set(-5.43, 1.47 + i * 0.075, 0); q.updateMatrix(); grill.setMatrixAt(i, q.matrix); }
  root.add(grill);
  const radCore = mesh(new THREE.BoxGeometry(0.05, 0.82, 1.65), M.grille, root, V(-5.4, 1.85, 0));
  add('sogutma', radCore); add('sogutma', grill); add('sogutma', radFrame);
  mesh(rbox(0.75, 0.85, 2.7, 0.1), M.paint, root, V(-5.05, 0.95, 0));           // karşı ağırlık
  mesh(new THREE.BoxGeometry(0.02, 0.16, 2.2), M.hazard, root, V(-5.435, 0.72, 0));
  for (const z of [1.15, -1.15]) {
    mesh(rbox(0.06, 0.12, 0.22, 0.02), M.lampRed, root, V(-5.43, 1.12, z));
    mesh(new THREE.CircleGeometry(0.05, 16).rotateY(-Math.PI / 2), M.lamp, root, V(-5.44, 1.32, z));
  }

  // ── Bom (kaldırma kolları) + kepçe
  const boom = new THREE.Group(); boom.position.set(1.0, 2.15, 0); root.add(boom);
  const L = 3.5, TIP = new THREE.Vector2(L, -1.45);
  const armPts = [[-0.25, 0.22], [1.4, 0.34], [2.7, -0.15], [3.65, -1.2], [3.55, -1.68], [2.5, -0.72],
    [1.3, -0.24], [-0.2, -0.3]].map(([x, y]) => new THREE.Vector2(x, y));
  for (const z of [0.62, -0.62]) mesh(plateFromOutline(armPts, 0.2), M.paint, boom, V(0, 0, z));
  mesh(cylZ(0.11, 0.11, 1.45, 20), M.paint, boom, V(1.6, 0.05, 0));             // çapraz boru
  for (const z of [0.62, -0.62]) mesh(cylZ(0.13, 0.13, 0.3, 20), M.chrome, boom, V(0, 0, z));

  const bucket = new THREE.Group(); bucket.position.set(TIP.x, TIP.y, 0); boom.add(bucket);
  const prof = [[0.55, 1.42], [0.05, 1.38], [-0.3, 1.18], [-0.38, 0.8], [-0.34, 0.42], [-0.18, 0.14],
    [0.15, -0.02], [0.8, -0.06], [1.5, -0.04], [1.85, 0.03]].map(([x, y]) => new THREE.Vector2(x, y - 0.5));
  const BW = 3.3;
  const shell = mesh(shellFromProfile(prof, 0.08, BW), M.paint, bucket);
  for (const z of [BW / 2, -BW / 2]) {
    const sp = [...prof, new THREE.Vector2(1.2, 0.35 - 0.5), new THREE.Vector2(0.8, 0.95 - 0.5)];
    mesh(plateFromOutline(sp, 0.07), M.paint, bucket, V(0, 0, z));
  }
  mesh(new THREE.BoxGeometry(0.25, 0.05, BW), M.steel, bucket, V(1.82, -0.46, 0));     // bıçak
  const tooth = new THREE.BoxGeometry(0.22, 0.07, 0.17);
  for (let i = 0; i < 9; i++) mesh(tooth, M.steel, bucket, V(1.95, -0.45, -1.45 + i * 0.3625));
  mesh(rbox(0.3, 0.25, 0.9, 0.04), M.paint, bucket, V(-0.32, 0.72, 0));               // devirme kulağı
  const pile = new THREE.SphereGeometry(1, 28, 16, 0, Math.PI * 2, 0, Math.PI / 2);
  const pos = pile.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const k = 1 + 0.18 * Math.sin(pos.getX(i) * 9.1) * Math.cos(pos.getZ(i) * 7.3);
    pos.setXYZ(i, pos.getX(i) * k, pos.getY(i) * k, pos.getZ(i) * k);
  }
  pile.computeVertexNormals();
  const load = mesh(pile, M.rock, bucket, V(0.55, -0.4, 0)); load.scale.set(0.95, 0.6, 1.5);
  shell.castShadow = true;

  // Silindirler (her karede uç noktalarına göre yerleştirilir)
  const cyl = (rb, rr) => {
    const g = new THREE.Group(); root.add(g);
    const barrel = mesh(new THREE.CylinderGeometry(rb, rb, 1, 20), M.paint, g);
    const rod = mesh(new THREE.CylinderGeometry(rr, rr, 1, 16), M.chrome, g);
    return { barrel, rod };
  };
  const lifts = [cyl(0.13, 0.07), cyl(0.13, 0.07)];
  const tilt = cyl(0.15, 0.08);

  const st = { boomA: 0, bucketA: 0.1, init: false };
  function animate(dt, S) {
    const [bt, kt] = POSE[S.phase] || POSE.idle;
    const moving = !st.init || Math.abs(bt - st.boomA) > 1e-3 || Math.abs(kt - st.bucketA) > 1e-3 || load.visible !== S.loaded;
    if (!moving) return false;
    st.init = true;
    st.boomA += (bt - st.boomA) * Math.min(1, dt * 1.4);
    st.bucketA += (kt - st.bucketA) * Math.min(1, dt * 1.6);
    boom.rotation.z = st.boomA;
    bucket.rotation.z = st.bucketA - st.boomA;
    load.visible = S.loaded;
    root.updateMatrixWorld(true);
    for (const [i, z] of [0.42, -0.42].entries()) {
      const p1 = boom.localToWorld(_b.set(1.75, -0.28, z)).clone();
      root.worldToLocal(p1);
      placeCylinder(lifts[i], _a.set(1.55, 1.05, z).clone(), p1);
    }
    const p1 = bucket.localToWorld(_b.set(-0.32, 0.8, 0)).clone();
    root.worldToLocal(p1);
    placeCylinder(tilt, _a.set(1.05, 2.45, 0).clone(), p1);
    return true;
  }
  return { root, parts, wheels, animate, offsetX: -0.2 };
}

// ─────────────────────────────────────────────────────────────────
// Kamyon modeli (TH551i benzeri, mafsallı, arkadan devirmeli damper)
// ─────────────────────────────────────────────────────────────────
function buildTruck(M) {
  const root = new THREE.Group();
  const parts = {};
  const add = (k, m) => { (parts[k] = parts[k] || []).push(m); return m; };
  const AX_F = 3.3, AX_R = -2.3, WS = 1.08, WY = 0.98 * WS, WZ = 1.25;
  const q = new THREE.Object3D();

  // ── Tekerlekler (ön çamurluklu; arka tekerlekler damperin altında)
  const wheels = [];
  for (const [x, z] of [[AX_F, WZ], [AX_F, -WZ], [AX_R, WZ], [AX_R, -WZ]]) {
    const w = buildWheel(M, Math.sign(z));
    w.scale.setScalar(WS);
    w.position.set(x, WY, z);
    root.add(w); wheels.push(w);
    add(x > 0 ? 'rulman' : 'fren', w.getObjectByName('hub'));
    if (x > 0) mesh(arcPlate(1.16, 1.24, 0.2, Math.PI - 0.2, 0.92), M.paint, root, V(x, WY, z));
  }
  for (const x of [AX_F, AX_R]) {
    const k = x > 0 ? 'rulman' : 'fren';
    add(k, mesh(cylZ(0.21, 0.21, 2.1, 24), M.frame, root, V(x, WY, 0)));
    add(k, mesh(new THREE.SphereGeometry(0.38, 24, 16), M.frame, root, V(x, WY, 0)));
    for (const z of [0.82, -0.82]) add(k, mesh(cylZ(0.36, 0.32, 0.2, 28), M.steel, root, V(x, WY, z)));
  }

  // ── Ön şasi, tampon, farlar
  mesh(rbox(3.6, 0.7, 1.3, 0.08), M.paint, root, V(3.5, 1.3, 0));
  mesh(rbox(0.55, 0.8, 3.0, 0.1), M.paint, root, V(5.35, 1.0, 0));
  mesh(new THREE.BoxGeometry(0.02, 0.16, 2.6), M.hazard, root, V(5.63, 0.8, 0));
  for (const z of [1.15, -1.15]) {
    mesh(rbox(0.12, 0.22, 0.3, 0.03), M.frame, root, V(5.62, 1.22, z));
    mesh(new THREE.CircleGeometry(0.08, 20).rotateY(Math.PI / 2), M.lamp, root, V(5.69, 1.22, z));
  }

  // ── Motor bölmesi (sol, −z) — kaput saydamlaşabilir
  const hood = new THREE.Group(); root.add(hood);
  mesh(rbox(2.6, 1.15, 1.35, 0.14), M.hood, hood, V(3.65, 2.05, -0.78));
  const vent = new THREE.InstancedMesh(new THREE.BoxGeometry(0.06, 0.03, 0.9), M.grille, 12);
  for (let i = 0; i < 12; i++) { q.position.set(2.85 + i * 0.12, 2.635, -0.78); q.updateMatrix(); vent.setMatrixAt(i, q.matrix); }
  hood.add(vent);
  mesh(new THREE.CylinderGeometry(0.1, 0.1, 0.7, 16), M.frame, hood, V(2.65, 2.9, -1.25));   // egzoz
  const radFrame = mesh(rbox(0.12, 0.95, 1.2, 0.04), M.paint, root, V(5.0, 2.0, -0.78));
  const grill = new THREE.InstancedMesh(new THREE.BoxGeometry(0.04, 0.035, 1.02), M.grille, 11);
  for (let i = 0; i < 11; i++) { q.position.set(5.07, 1.62 + i * 0.075, -0.78); q.updateMatrix(); grill.setMatrixAt(i, q.matrix); }
  root.add(grill);
  const radCore = mesh(new THREE.BoxGeometry(0.05, 0.8, 1.05), M.grille, root, V(5.04, 2.0, -0.78));
  add('sogutma', radCore); add('sogutma', grill); add('sogutma', radFrame);
  const engine = new THREE.Group(); root.add(engine);
  add('motor_isi', mesh(rbox(1.6, 0.7, 0.85, 0.06), M.engine, engine, V(3.5, 1.95, -0.78)));
  add('motor_isi', mesh(rbox(1.4, 0.16, 0.6, 0.04), M.steel, engine, V(3.5, 2.36, -0.78)));
  for (let i = 0; i < 6; i++)
    add('enjektor', mesh(new THREE.CylinderGeometry(0.045, 0.045, 0.16, 12), M.chrome, engine, V(2.95 + i * 0.25, 2.5, -0.66)));
  add('enjektor', mesh(cylX(0.03, 0.03, 1.45, 8), M.steel, engine, V(3.6, 2.55, -0.56)));
  add('motor_sargi', mesh(cylX(0.2, 0.2, 0.42, 24), M.steel, engine, V(4.45, 1.7, -0.3)));
  add('motor_sargi', mesh(new THREE.TorusGeometry(0.2, 0.025, 8, 24).rotateY(Math.PI / 2), M.chrome, engine, V(4.68, 1.7, -0.3)));

  // ── Kabin (sağ, +z): beyaz, alt eteği turuncu
  const cab = new THREE.Group(); cab.position.set(4.05, 0, 0.8); root.add(cab);
  mesh(rbox(1.75, 0.42, 1.3, 0.06), M.paint, cab, V(0, 1.42, 0));
  mesh(rbox(1.7, 1.5, 1.25, 0.1), M.cab, cab, V(0, 2.35, 0));
  mesh(rbox(1.82, 0.12, 1.37, 0.05), M.cab, cab, V(0, 3.15, 0));
  mesh(rbox(0.04, 0.8, 1.0, 0.02), M.glass, cab, V(0.86, 2.55, 0));
  mesh(rbox(0.04, 0.8, 1.0, 0.02), M.glass, cab, V(-0.86, 2.55, 0));
  mesh(rbox(1.3, 0.8, 0.04, 0.02), M.glass, cab, V(0.05, 2.55, 0.63));
  mesh(rbox(1.35, 0.1, 0.05, 0.02), M.frame, cab, V(0.0, 2.08, 0.635));
  for (const z of [-0.4, 0.4]) {
    mesh(rbox(0.16, 0.14, 0.24, 0.03), M.frame, cab, V(0.84, 3.28, z));
    mesh(new THREE.CircleGeometry(0.06, 16).rotateY(Math.PI / 2), M.lamp, cab, V(0.925, 3.28, z));
  }
  mesh(new THREE.CylinderGeometry(0.07, 0.08, 0.12, 16), M.beacon, cab, V(-0.6, 3.27, 0.3));
  const lad = new THREE.Group(); lad.position.set(0.55, 0, 0.7); cab.add(lad);
  for (const dx of [-0.2, 0.2]) mesh(cylX(0.022, 0.022, 0.95, 8).rotateZ(Math.PI / 2), M.yellow, lad, V(dx, 0.95, 0));
  for (const y of [0.6, 0.9, 1.2]) mesh(new THREE.BoxGeometry(0.42, 0.04, 0.14), M.yellow, lad, V(0, y, 0));

  // ── Mafsal
  mesh(rbox(0.7, 0.85, 1.0, 0.06), M.frame, root, V(1.7, 1.2, 0));
  for (const y of [0.7, 1.7]) mesh(new THREE.CylinderGeometry(0.13, 0.13, 0.25, 20), M.chrome, root, V(1.7, y, 0));
  for (const z of [0.5, -0.5]) {
    const c = mesh(cylX(0.06, 0.06, 1.1, 14), M.chrome, root, V(1.75, 1.05, z));
    c.rotation.y = z > 0 ? 0.25 : -0.25;
  }

  // ── Arka şasi, şanzıman, şaft, damper pompası
  for (const z of [0.55, -0.55]) mesh(rbox(5.9, 0.55, 0.2, 0.04), M.paint, root, V(-1.55, 1.15, z));
  mesh(rbox(0.45, 0.65, 2.5, 0.06), M.paint, root, V(-4.55, 1.15, 0));
  mesh(new THREE.BoxGeometry(0.02, 0.15, 2.0), M.hazard, root, V(-4.785, 1.0, 0));
  for (const z of [1.1, -1.1]) {
    mesh(rbox(0.06, 0.14, 0.24, 0.02), M.lampRed, root, V(-4.8, 1.3, z));
    mesh(new THREE.CircleGeometry(0.05, 16).rotateY(-Math.PI / 2), M.lamp, root, V(-4.81, 1.05, z));
  }
  add('transmisyon', mesh(rbox(0.9, 0.55, 0.75, 0.07), M.steel, root, V(0.75, 1.0, 0)));
  add('transmisyon', mesh(cylX(0.3, 0.3, 0.3, 28), M.steel, root, V(1.3, 1.0, 0)));
  add('transmisyon', mesh(cylX(0.07, 0.07, 2.4, 16), M.steel, root, V(-0.95, 0.98, 0)));
  add('hidrolik_pompa', mesh(cylX(0.2, 0.2, 0.5, 24), M.engine, root, V(0.0, 1.0, 0.86)));
  add('hidrolik_pompa', mesh(rbox(0.32, 0.3, 0.3, 0.04), M.engine, root, V(-0.33, 1.0, 0.86)));
  for (const [i, pts] of [
    [V(0.15, 1.1, 0.86), V(0.45, 1.35, 0.9), V(0.6, 1.3, 0.85)],
    [V(-0.35, 1.15, 0.86), V(-0.2, 1.5, 0.3), V(0.3, 1.35, -0.6), V(0.6, 1.3, -0.8)],
    [V(0.05, 0.85, 0.9), V(0.9, 0.95, 0.8), V(1.6, 1.15, 0.5)],
  ].entries())
    add('hidrolik_pompa', mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 32, i === 1 ? 0.045 : 0.035, 10), M.hose, root));

  // ── Damper kasası (arka menteşeden döner)
  const box = new THREE.Group(); box.position.set(-4.3, 1.95, 0); root.add(box);
  const BL = 6.1, top = (x) => 1.05 + (x - 0.4) * 0.11;
  mesh(rbox(BL, 0.14, 3.1, 0.04), M.paint, box, V(BL / 2, 0.07, 0));
  const side = [[0, 0], [BL, 0], [BL, 1.6], [5.6, top(5.6)], [0.4, top(0.4)], [0, 0.9]].map(([x, y]) => new THREE.Vector2(x, y));
  for (const z of [1.55, -1.55]) {
    mesh(plateFromOutline(side, 0.1), M.paint, box, V(0, 0, z));
    const rail = mesh(rbox(5.35, 0.16, 0.2, 0.05), M.paint, box, V(3.0, (top(0.4) + top(5.6)) / 2, z * 1.03));
    rail.rotation.z = Math.atan(0.11);
    for (const x of [1.2, 2.3, 3.4, 4.5]) {
      const h = top(x) - 0.1;
      mesh(rbox(0.12, h, 0.08, 0.03), M.paint, box, V(x, h / 2 + 0.02, z * 1.05));
    }
    mesh(new THREE.BoxGeometry(0.9, 0.14, 0.02), M.hazard, box, V(0.9, top(0.9) - 0.18, z * 1.075));
  }
  mesh(rbox(0.14, 1.75, 3.3, 0.04), M.paint, box, V(BL - 0.05, 0.87, 0));
  const lip = mesh(rbox(1.0, 0.1, 3.3, 0.04), M.paint, box, V(BL + 0.35, 1.9, 0));
  lip.rotation.z = 0.42;
  mesh(new THREE.BoxGeometry(0.02, 0.17, 3.0), M.hazard, box, V(BL + 0.02, 1.45, 0));
  const tail = mesh(rbox(0.55, 0.12, 3.1, 0.04), M.paint, box, V(0.1, 0.16, 0));
  tail.rotation.z = -0.35;
  for (const z of [0.8, -0.8]) mesh(rbox(5.8, 0.18, 0.18, 0.04), M.frame, box, V(3.0, -0.09, z));
  for (const z of [0.8, -0.8]) mesh(cylZ(0.12, 0.12, 0.3, 20), M.chrome, root, V(-4.3, 1.85, z));
  const pile = new THREE.SphereGeometry(1, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2);
  const pp = pile.attributes.position;
  for (let i = 0; i < pp.count; i++) {
    const k = 1 + 0.12 * Math.sin(pp.getX(i) * 11.3) * Math.cos(pp.getZ(i) * 8.7);
    pp.setXYZ(i, pp.getX(i) * k, pp.getY(i) * k, pp.getZ(i) * k);
  }
  pile.computeVertexNormals();
  const load = mesh(pile, M.rock, box, V(3.3, 0.1, 0)); load.scale.set(2.7, 0.95, 1.4);

  // Devirme silindirleri (şasiden kasa altına)
  const cyl = () => {
    const g = new THREE.Group(); root.add(g);
    return { barrel: mesh(new THREE.CylinderGeometry(0.15, 0.15, 1, 20), M.paint, g),
             rod: mesh(new THREE.CylinderGeometry(0.085, 0.085, 1, 16), M.chrome, g) };
  };
  const hoists = [cyl(), cyl()];

  const st = { a: 0, init: false };
  function animate(dt, S) {
    const want = S.phase === 'dumping' ? 0.85 : 0;
    const moving = !st.init || Math.abs(want - st.a) > 1e-3 || load.visible !== S.loaded;
    if (!moving) return false;
    st.init = true;
    st.a += (want - st.a) * Math.min(1, dt * 1.2);
    box.rotation.z = st.a;
    load.visible = S.loaded && st.a < 0.3;
    root.updateMatrixWorld(true);
    for (const [i, z] of [0.85, -0.85].entries()) {
      const p1 = box.localToWorld(_b.set(3.7, -0.15, z)).clone();
      root.worldToLocal(p1);
      placeCylinder(hoists[i], _a.set(0.55, 1.25, z).clone(), p1);
    }
    return true;
  }
  return { root, parts, wheels, animate, offsetX: -0.4 };
}

const VEHICLES = {
  loader: { build: buildLoader, comp: COMP_LOADER, home: HOME_LOADER,
            tags: { motor: V(-3.9, 2.6, 0), hyd: V(2.8, 2.6, 0), sasi: V(2.5, 2.25, 1.2) } },
  truck:  { build: buildTruck, comp: COMP_TRUCK, home: HOME_TRUCK,
            tags: { motor: V(3.6, 2.9, -0.78), hyd: V(0.2, 1.6, 1.0), sasi: V(3.3, 2.45, 1.3) } },
};

const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _d = new THREE.Vector3(), _up = new THREE.Vector3(0, 1, 0);
function placeCylinder(c, p0, p1) {
  _d.subVectors(p1, p0); const len = _d.length(); _d.normalize();
  const q = new THREE.Quaternion().setFromUnitVectors(_up, _d);
  const bl = len * 0.62, rl = len * 0.5;
  c.barrel.scale.set(1, bl, 1); c.barrel.quaternion.copy(q);
  c.barrel.position.copy(p0).addScaledVector(_d, bl / 2);
  c.rod.scale.set(1, rl, 1); c.rod.quaternion.copy(q);
  c.rod.position.copy(p1).addScaledVector(_d, -rl / 2);
}

// ─────────────────────────────────────────────────────────────────
// Sahne
// ─────────────────────────────────────────────────────────────────
const CSS = `
.t3-wrap{position:relative;width:100%;height:420px;border-radius:8px;overflow:hidden;background:#0b0d10}
.t3-wrap canvas{display:block;width:100%;height:100%;cursor:grab}
.t3-tag{position:absolute;left:0;top:0;pointer-events:none;font:600 11px/1.35 system-ui,-apple-system,sans-serif;
  color:#e9ecef;background:rgba(14,17,21,.72);border:1px solid rgba(255,255,255,.12);border-radius:6px;
  padding:4px 7px;white-space:nowrap;transform:translate(-50%,-130%);backdrop-filter:blur(4px);transition:opacity .4s}
.t3-tag b{color:#9aa4ae;font-weight:600;letter-spacing:.6px;font-size:9.5px;display:block;text-transform:uppercase}
.t3-focus{position:absolute;left:0;top:0;pointer-events:none;transition:opacity .5s;opacity:0}
.t3-dot{position:absolute;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;background:var(--t3c,#ff3b30);
  box-shadow:0 0 0 0 var(--t3c,#ff3b30);animation:t3p 1.4s infinite}
@keyframes t3p{0%{box-shadow:0 0 0 0 rgba(255,59,48,.7)}100%{box-shadow:0 0 0 18px rgba(255,59,48,0)}}
.t3-card{position:absolute;left:26px;top:-70px;min-width:220px;max-width:300px;background:rgba(14,17,21,.86);
  border:1px solid var(--t3c,#ff3b30);border-left:4px solid var(--t3c,#ff3b30);border-radius:8px;padding:9px 12px;
  color:#eef1f4;font:12px/1.45 system-ui,-apple-system,sans-serif;backdrop-filter:blur(6px)}
.t3-card .t{font-weight:700;font-size:13px;color:var(--t3c,#ff3b30)}
.t3-card .s{color:#aab3bc;font-size:11px}
.t3-line{position:absolute;left:0;top:0;width:26px;height:1px;background:var(--t3c,#ff3b30);transform-origin:0 0;rotate:-70deg}
.t3-ctl{position:absolute;right:10px;bottom:10px;display:flex;gap:6px}
.t3-ctl button{height:30px;padding:0 10px;border-radius:7px;border:1px solid rgba(255,255,255,.14);
  background:rgba(20,23,27,.8);color:#e9ecef;font-size:11.5px;cursor:pointer}
.t3-ctl button:hover{background:rgba(40,44,50,.9)}
.t3-mode{position:absolute;left:12px;bottom:12px;font:600 10px system-ui;letter-spacing:1px;color:#7d8893;text-transform:uppercase}
`;

export function mount(el, tip = 'loader') {
  unmount();
  if (!document.getElementById('t3-css')) {
    const st = document.createElement('style'); st.id = 't3-css'; st.textContent = CSS; document.head.appendChild(st);
  }
  el.innerHTML = '';
  const wrap = document.createElement('div'); wrap.className = 't3-wrap'; el.appendChild(wrap);

  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  wrap.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x060708);
  const cfg = VEHICLES[tip] || VEHICLES.loader;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = envTex;
  scene.environmentIntensity = 0.55;

  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 120);
  camera.position.copy(cfg.home.cam);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.copy(cfg.home.tgt);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.minDistance = 3.2; controls.maxDistance = 24;
  controls.maxPolarAngle = Math.PI * 0.495; controls.enablePan = true;
  controls.update();

  const M = makeMaterials();
  // Işık: stüdyo düzeni — gölgeli ana ışık, dolgu, arka kontur, üstten yumuşak spot
  scene.add(new THREE.HemisphereLight(0xc8d2dc, 0x1a1a1c, 0.45));
  const key = new THREE.DirectionalLight(0xfff4e8, 2.6);
  key.position.set(7, 13, 9); key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -9, right: 9, top: 8, bottom: -6, near: 1, far: 40 });
  key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 5;
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xc4d6ff, 0.6); fill.position.set(-8, 5, -7); scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.9); rim.position.set(-9, 6, 6); scene.add(rim);
  const top = new THREE.SpotLight(0xffffff, 140, 30, 0.7, 1.0, 1.6);
  top.position.set(0, 13, 2); top.target.position.set(0, 0, 0); scene.add(top, top.target);

  // Düz stüdyo zemini (kenarlarda siyah fona erir)
  const floor = mesh(new THREE.CircleGeometry(16, 96).rotateX(-Math.PI / 2), M.floor, scene);
  floor.castShadow = false;

  const model = cfg.build(M);
  model.root.position.x = model.offsetX;
  scene.add(model.root);

  // Etiketler
  const tags = {
    motor: makeTag(wrap, 'Motor · yağ sıc. · akım'),
    hyd:   makeTag(wrap, 'Hidrolik basınç'),
    sasi:  makeTag(wrap, 'Şasi · titreşim · hız'),
  };
  const tagAnchors = cfg.tags;
  const focusEl = document.createElement('div'); focusEl.className = 't3-focus';
  focusEl.innerHTML = '<div class="t3-dot"></div><div class="t3-line"></div><div class="t3-card"><div class="t"></div><div class="s"></div><div class="r"></div></div>';
  wrap.appendChild(focusEl);
  const glow = new THREE.PointLight(0xff3020, 0, 3.5, 2); scene.add(glow);

  const ctl = document.createElement('div'); ctl.className = 't3-ctl';
  ctl.innerHTML = '<button data-a="home">Genel görünüm</button><button data-a="focus">Arızaya odaklan</button>';
  wrap.appendChild(ctl);
  const mode = document.createElement('div'); mode.className = 't3-mode'; mode.textContent = '3B dijital ikiz'; wrap.appendChild(mode);

  S = {
    el, wrap, renderer, scene, camera, controls, M, model, cfg, tags, tagAnchors, focusEl, glow, envTex, pmrem,
    speed: 0, phase: 'idle', loaded: false,
    focus: null, tween: null, userMoved: false, dirty: true, clock: new THREE.Clock(), raf: 0, visible: true,
  };
  ctl.addEventListener('click', (e) => {
    const a = e.target.dataset.a;
    if (a === 'home') { S.userMoved = true; flyTo(S.cfg.home.cam, S.cfg.home.tgt, 1.3); }
    if (a === 'focus' && S.focus) { const c = S.cfg.comp[S.focus.key]; S.userMoved = false; flyTo(c.cam, c.tgt, 1.6); }
  });
  controls.addEventListener('start', () => { S.userMoved = true; S.tween = null; });
  controls.addEventListener('change', () => { S.dirty = true; });

  const ro = new ResizeObserver(resize); ro.observe(wrap); S.ro = ro;
  const io = new IntersectionObserver((en) => { S.visible = en[0].isIntersecting; S.dirty = true; }); io.observe(wrap); S.io = io;
  resize();
  loop();
  return true;
}

function makeTag(wrap, title) {
  const d = document.createElement('div'); d.className = 't3-tag';
  d.innerHTML = `<b>${title}</b><span>—</span>`;
  wrap.appendChild(d);
  return d;
}

function resize() {
  if (!S) return;
  const w = S.wrap.clientWidth, h = S.wrap.clientHeight;
  if (!w || !h) return;
  S.renderer.setSize(w, h, false);
  S.camera.aspect = w / h;
  S.camera.updateProjectionMatrix();
  S.dirty = true;
}

const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
function flyTo(cam, tgt, dur) {
  const off = S.model.root.position;
  S.tween = { start: performance.now(), dur, c0: S.camera.position.clone(), t0: S.controls.target.clone(),
    c1: cam.clone().add(off), t1: tgt.clone().add(off) };
}

function setHighlight(key, color) {
  // önceki vurguyu temizle
  for (const m of S.hl || []) { m.material = m.userData.orig; }
  S.hl = [];
  if (!key) return;
  for (const m of S.model.parts[key] || []) {
    if (!m.userData.orig) m.userData.orig = m.material;
    const mat = m.userData.orig.clone();
    mat.emissive = new THREE.Color(color); mat.emissiveIntensity = 0.8;
    m.material = mat; S.hl.push(m);
  }
}

function loop() {
  S.raf = requestAnimationFrame(loop);
  const dt = Math.min(S.clock.getDelta(), 0.1);
  if (document.hidden || !S.visible) return;
  const t = S.clock.elapsedTime;
  const md = S.model;
  const comp = S.focus ? S.cfg.comp[S.focus.key] : null;
  const want = comp && comp.ic ? 0.16 : 1;
  const hm = S.M.hood;
  // Araç stantta: tekerlek dönmez; yalnız faz duruşu (bom/kepçe ya da damper) değişince hareket var
  const moving = md.animate(dt, S) || Math.abs(want - hm.opacity) > 1e-3;
  // Sahne durgunsa hiç çizme (GPU boşta kalır); yalnız hareket/odak/kamera değişince çiz
  if (!moving && !S.tween && !S.focus && !S.dirty) return;
  S.dirty = false;

  // kamera geçişi
  if (S.tween) {
    const p = (performance.now() - S.tween.start) / 1000 / S.tween.dur;
    const k = ease(Math.min(1, p));
    S.camera.position.lerpVectors(S.tween.c0, S.tween.c1, k);
    S.controls.target.lerpVectors(S.tween.t0, S.tween.t1, k);
    if (p >= 1) S.tween = null;
  }
  S.controls.update();

  // odak: nabız gibi parlama + iç parçada kaput saydamlığı
  hm.opacity += (want - hm.opacity) * Math.min(1, dt * 3);
  hm.depthWrite = hm.opacity > 0.95;
  if (S.focus) {
    const pulse = 0.55 + 0.45 * Math.sin(t * 4.2);
    for (const m of S.hl) m.material.emissiveIntensity = 0.4 + 1.6 * pulse;
    S.glow.intensity = 6 + 10 * pulse;
  } else S.glow.intensity = 0;

  // etiketler
  const w = S.wrap.clientWidth, h = S.wrap.clientHeight, off = md.root.position;
  const proj = (p) => { const v = p.clone().add(off).project(S.camera); return [(v.x + 1) / 2 * w, (1 - v.y) / 2 * h, v.z < 1]; };
  const dist = S.camera.position.distanceTo(S.controls.target);
  for (const k in S.tags) {
    const [x, y, ok] = proj(S.tagAnchors[k]);
    const el = S.tags[k];
    el.style.left = x + 'px'; el.style.top = y + 'px';
    el.style.opacity = (ok && !S.focus && dist > 9) ? 1 : 0;
  }
  if (S.focus) {
    const [x, y, ok] = proj(comp.tgt);
    S.focusEl.style.transform = `translate(${x}px,${y}px)`;
    S.focusEl.style.opacity = ok ? 1 : 0;
    // parıltı ışığı bileşenin kameraya bakan tarafında
    S.glow.position.copy(comp.tgt).addScaledVector(_d.subVectors(comp.cam, comp.tgt).normalize(), 0.7).add(off);
  } else S.focusEl.style.opacity = 0;

  S.renderer.render(S.scene, S.camera);
}

export function update(d) {
  if (!S || !d) return;
  S.speed = Number(d.speed) || 0;
  S.phase = d.phase || 'idle';
  S.loaded = LOADED.has(S.phase);
  S.dirty = true;
  const set = (k, txt) => { S.tags[k].querySelector('span').textContent = txt; };
  if (d.temperature != null) set('motor', `${(+d.temperature).toFixed(1)} °C · ${(+d.current).toFixed(0)} A`);
  if (d.pressure != null) set('hyd', `${(+d.pressure).toFixed(0)} bar`);
  if (d.vibration != null) set('sasi', `${(+d.vibration).toFixed(2)} mm/s · ${(+d.speed).toFixed(1)} km/h`);
}

/** bilgi: {renk:'kirmizi'|'sari', baslik, alt, rul} */
export function focus(key, bilgi = {}) {
  const C = S && S.cfg.comp[key];
  if (!C) return;
  const color = bilgi.renk === 'sari' ? '#ffb020' : '#ff3b30';
  const card = S.focusEl.querySelector('.t3-card');
  S.focusEl.style.setProperty('--t3c', color);
  card.querySelector('.t').textContent = bilgi.baslik || C.ad;
  card.querySelector('.s').textContent = bilgi.alt || C.yer;
  card.querySelector('.r').textContent = bilgi.rul || '';
  const changed = !S.focus || S.focus.key !== key || S.focus.color !== color;
  S.focus = { key, color };
  if (changed) {
    setHighlight(key, color);
    S.glow.color.set(color);
    S.userMoved = false;
    flyTo(C.cam, C.tgt, 1.8);
  }
}

export function clearFocus() {
  if (!S || !S.focus) return;
  S.focus = null;
  setHighlight(null);
  S.dirty = true;
  if (!S.userMoved) flyTo(S.cfg.home.cam, S.cfg.home.tgt, 1.6);
}

export function unmount() {
  if (!S) return;
  cancelAnimationFrame(S.raf);
  S.ro.disconnect(); S.io.disconnect();
  S.controls.dispose();
  S.scene.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
    for (const m of mats) { if (m.map) m.map.dispose(); if (m.alphaMap) m.alphaMap.dispose(); m.dispose(); }
  });
  S.envTex.dispose(); S.pmrem.dispose();
  S.renderer.dispose();
  S.renderer.forceContextLoss();
  S.el.innerHTML = '';
  S = null;
}

window.Twin3D = { supported, mount, update, focus, clearFocus, unmount,
  _durum: () => S && { cam: S.camera.position.toArray().map((v) => +v.toFixed(2)), tween: !!S.tween, focus: S.focus } };
window.dispatchEvent(new Event('twin3d-ready'));
