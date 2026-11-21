/*
 * 3B Dijital İkiz — Sandvik LH517i benzeri yeraltı yükleyici (LHD)
 * ─────────────────────────────────────────────────────────────────
 * Model tamamen koddan üretilir (dış model/marka/logo yok); ölçüler üretici
 * verisine yakındır: ~11,8 m boy, 3,1 m en, 2,8 m yükseklik, ~1,95 m lastik.
 *
 *   Twin3D.supported()                 → WebGL var mı
 *   Twin3D.mount(el, tip)              → sahneyi kur (tip: "loader")
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
const COMP = {
  rulman:         { ad: 'Rulman aşınması',            yer: 'Ön aks — tekerlek göbeği',  cam: V(5.6, 1.5, 5.2),  tgt: V(2.5, 1.0, 1.2),  ic: false },
  fren:           { ad: 'Fren sürtmesi / ısınma',      yer: 'Arka aks — ıslak disk fren', cam: V(0.6, 1.4, 5.0),  tgt: V(-1.9, 1.0, 1.2), ic: false },
  hidrolik_pompa: { ad: 'Hidrolik pompa arızası',      yer: 'Hidrolik sistem — pompa',    cam: V(-1.3, 1.35, 5.0), tgt: V(-0.15, 0.95, 0.62), ic: false },
  transmisyon:    { ad: 'Transmisyon arızası',         yer: 'Güç aktarma — şanzıman',     cam: V(-0.75, 0.65, 4.5), tgt: V(-0.8, 0.9, 0.0), ic: false },
  motor_isi:      { ad: 'Motor aşırı ısınması',        yer: 'Motor bloğu',                cam: V(-2.0, 4.4, 5.4), tgt: V(-3.7, 1.8, 0.0), ic: true  },
  enjektor:       { ad: 'Enjektör / yanma arızası',    yer: 'Motor — enjektör hattı',     cam: V(-2.6, 4.6, 3.4), tgt: V(-3.7, 2.15, 0.0), ic: true },
  motor_sargi:    { ad: 'Tahrik motoru sargı arızası', yer: 'Tahrik motoru / alternatör', cam: V(-1.2, 2.8, 4.4), tgt: V(-2.75, 1.65, 0.55), ic: true },
  sogutma:        { ad: 'Soğutma sistemi arızası',     yer: 'Radyatör / fan',             cam: V(-9.6, 2.4, 3.8), tgt: V(-5.3, 1.7, 0.0), ic: false },
};
const HOME = { cam: V(5.8, 3.3, 12.6), tgt: V(-0.3, 1.25, 0) };

// ── Faz → bom / kepçe açısı (radyan): canlı fazı fiziksel harekete çevirir
const POSE = {
  idle:            [0.00, 0.10], approach_pile:  [-0.04, 0.02],
  picking_up:      [0.10, 0.42], hauling_loaded: [0.16, 0.55],
  approach_dump:   [0.50, 0.50], dumping:        [0.62, -0.62],
  returning_empty: [0.05, 0.18], kotu_yol:       [0.16, 0.55],
};
const LOADED = new Set(['picking_up', 'hauling_loaded', 'approach_dump', 'kotu_yol']);

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
    ground:   std({ map: noiseTexture(512, [70, 65, 60], 22, 3, 8), roughness: 0.97, metalness: 0.0 }),
    tunnel:   std({ map: noiseTexture(512, [74, 70, 66], 26, 11, 4), roughness: 0.98, metalness: 0.0,
                    side: THREE.BackSide }),
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
  const pump = mesh(cylX(0.2, 0.2, 0.5, 24), M.engine, root, V(0.0, 0.95, 0.62));
  const pumpBody = mesh(rbox(0.32, 0.3, 0.3, 0.04), M.engine, root, V(-0.32, 0.95, 0.62));
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

  return { root, parts, wheels, boom, bucket, load, lifts, tilt, hood, hoodMain };
}

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
  scene.background = new THREE.Color(0x0a0c0f);
  scene.fog = new THREE.Fog(0x0a0c0f, 22, 48);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = envTex;
  scene.environmentIntensity = 0.55;

  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 120);
  camera.position.copy(HOME.cam);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.copy(HOME.tgt);
  controls.enableDamping = true; controls.dampingFactor = 0.08;
  controls.minDistance = 3.2; controls.maxDistance = 22;
  controls.maxPolarAngle = Math.PI * 0.495; controls.enablePan = true;
  controls.update();

  const M = makeMaterials();
  // Işık: ana (gölgeli), dolgu, gök/yer, galeri lambaları
  scene.add(new THREE.HemisphereLight(0x9fb0c2, 0x2a241e, 0.55));
  const key = new THREE.DirectionalLight(0xfff2e2, 2.4);
  key.position.set(7, 13, 9); key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -9, right: 9, top: 7, bottom: -5, near: 1, far: 40 });
  key.shadow.bias = -0.0004; key.shadow.normalBias = 0.02; key.shadow.radius = 4;
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xb9cfff, 0.55); fill.position.set(-8, 5, -6); scene.add(fill);
  const rim = new THREE.DirectionalLight(0xffffff, 0.5); rim.position.set(-6, 4, 9); scene.add(rim);
  for (const x of [-12, 0, 12]) {
    const p = new THREE.PointLight(0xffd9a0, 18, 14, 2); p.position.set(x, 4.6, -1.5); scene.add(p);
  }
  const head = new THREE.SpotLight(0xfff4e0, 60, 20, 0.5, 0.6, 1.6);
  head.position.set(3.8, 2.2, 0); head.target.position.set(10, 0, 0); scene.add(head, head.target);

  // Zemin + galeri (kesit görünümü: yakın duvar kameradan saklanır)
  const ground = mesh(new THREE.PlaneGeometry(80, 80).rotateX(-Math.PI / 2), M.ground, scene);
  ground.castShadow = false;
  const tg = new THREE.CylinderGeometry(4.2, 4.2, 70, 64, 30, true, 0, Math.PI).rotateZ(Math.PI / 2).rotateX(-Math.PI / 2);
  const tp = tg.attributes.position;
  for (let i = 0; i < tp.count; i++) {
    const x = tp.getX(i), y = tp.getY(i), z = tp.getZ(i);
    const n = 0.18 * Math.sin(x * 1.3 + z * 2.1) + 0.12 * Math.sin(x * 3.7 - y * 2.9) + 0.07 * Math.sin(z * 6.1 + x * 5.3);
    const r = Math.hypot(y, z) || 1;
    tp.setXYZ(i, x, y + y / r * n, z + z / r * n);
  }
  tg.computeVertexNormals();
  const tunnel = mesh(tg, M.tunnel, scene, V(0, 0.6, 0)); tunnel.castShadow = false;
  // yerde kaya parçaları
  const rk = new THREE.InstancedMesh(new THREE.DodecahedronGeometry(0.18, 0), M.rock, 60);
  const q = new THREE.Object3D();
  let s = 42; const rnd = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 60; i++) {
    q.position.set(-20 + rnd() * 40, 0.05, (rnd() < 0.5 ? -1 : 1) * (2.2 + rnd() * 1.6));
    q.rotation.set(rnd() * 3, rnd() * 3, rnd() * 3); const k = 0.4 + rnd() * 1.6; q.scale.set(k, k * 0.6, k);
    q.updateMatrix(); rk.setMatrixAt(i, q.matrix);
  }
  rk.receiveShadow = true; scene.add(rk);
  // ileride malzeme yığını
  const heap = mesh(new THREE.SphereGeometry(2.4, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2), M.rock, scene, V(11.5, 0, 0));
  heap.scale.set(1.2, 0.75, 1.1);

  const model = buildLoader(M);
  model.root.position.x = -0.2;
  scene.add(model.root);

  // Etiketler
  const tags = {
    motor: makeTag(wrap, 'Motor · yağ sıc. · akım'),
    hyd:   makeTag(wrap, 'Hidrolik basınç'),
    sasi:  makeTag(wrap, 'Şasi · titreşim · hız'),
  };
  const tagAnchors = { motor: V(-3.9, 2.6, 0), hyd: V(2.8, 2.6, 0), sasi: V(2.5, 2.25, 1.2) };
  const focusEl = document.createElement('div'); focusEl.className = 't3-focus';
  focusEl.innerHTML = '<div class="t3-dot"></div><div class="t3-line"></div><div class="t3-card"><div class="t"></div><div class="s"></div><div class="r"></div></div>';
  wrap.appendChild(focusEl);
  const glow = new THREE.PointLight(0xff3020, 0, 3.5, 2); scene.add(glow);

  const ctl = document.createElement('div'); ctl.className = 't3-ctl';
  ctl.innerHTML = '<button data-a="home">Genel görünüm</button><button data-a="focus">Arızaya odaklan</button>';
  wrap.appendChild(ctl);
  const mode = document.createElement('div'); mode.className = 't3-mode'; mode.textContent = '3B dijital ikiz'; wrap.appendChild(mode);

  S = {
    el, wrap, renderer, scene, camera, controls, M, model, tags, tagAnchors, focusEl, glow, envTex, pmrem,
    speed: 0, phase: 'idle', boomA: 0, bucketA: 0.1, wheelA: 0, loaded: false,
    focus: null, tween: null, userMoved: false, dirty: true, clock: new THREE.Clock(), raf: 0, visible: true,
  };
  ctl.addEventListener('click', (e) => {
    const a = e.target.dataset.a;
    if (a === 'home') { S.userMoved = true; flyTo(HOME.cam, HOME.tgt, 1.3); }
    if (a === 'focus' && S.focus) { S.userMoved = false; flyTo(COMP[S.focus.key].cam, COMP[S.focus.key].tgt, 1.6); }
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
  const [bt0, kt0] = POSE[S.phase] || POSE.idle;
  const moving = S.speed > 0.05 || Math.abs(bt0 - S.boomA) > 1e-3 || Math.abs(kt0 - S.bucketA) > 1e-3
    || md.load.visible !== S.loaded || Math.abs((S.focus && COMP[S.focus.key].ic ? 0.16 : 1) - S.M.hood.opacity) > 1e-3;
  // Sahne durgunsa hiç çizme (GPU boşta kalır); yalnız hareket/odak/kamera değişince çiz
  if (!moving && !S.tween && !S.focus && !S.dirty) return;
  S.dirty = false;

  // tekerlek dönüşü (hız km/h → rad/s, r = 0.98 m)
  S.wheelA -= (S.speed / 3.6) / 0.98 * dt;
  for (const w of md.wheels) w.rotation.z = S.wheelA;
  // bom/kepçe fazı takip eder (yumuşak)
  const [bt, kt] = POSE[S.phase] || POSE.idle;
  S.boomA += (bt - S.boomA) * Math.min(1, dt * 1.4);
  S.bucketA += (kt - S.bucketA) * Math.min(1, dt * 1.6);
  md.boom.rotation.z = S.boomA;
  md.bucket.rotation.z = S.bucketA - S.boomA;
  md.load.visible = S.loaded;
  // silindirler
  md.root.updateMatrixWorld(true);
  for (const [i, z] of [0.42, -0.42].entries()) {
    const p0 = _a.set(1.55, 1.05, z).clone();
    const p1 = md.boom.localToWorld(_b.set(1.75, -0.28, z)).clone();
    md.root.worldToLocal(p1);
    placeCylinder(md.lifts[i], p0, p1);
  }
  {
    const p0 = _a.set(1.05, 2.45, 0).clone();
    const p1 = md.bucket.localToWorld(_b.set(-0.32, 0.8, 0)).clone();
    md.root.worldToLocal(p1);
    placeCylinder(md.tilt, p0, p1);
  }

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
  const want = S.focus && COMP[S.focus.key].ic ? 0.16 : 1;
  const hm = S.M.hood;
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
    const [x, y, ok] = proj(COMP[S.focus.key].tgt);
    S.focusEl.style.transform = `translate(${x}px,${y}px)`;
    S.focusEl.style.opacity = ok ? 1 : 0;
    S.glow.position.copy(COMP[S.focus.key].tgt).add(off).add(V(0, 0.4, 0.6));
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
  if (!S || !COMP[key]) return;
  const color = bilgi.renk === 'sari' ? '#ffb020' : '#ff3b30';
  const card = S.focusEl.querySelector('.t3-card');
  S.focusEl.style.setProperty('--t3c', color);
  card.querySelector('.t').textContent = bilgi.baslik || COMP[key].ad;
  card.querySelector('.s').textContent = bilgi.alt || COMP[key].yer;
  card.querySelector('.r').textContent = bilgi.rul || '';
  const changed = !S.focus || S.focus.key !== key || S.focus.color !== color;
  S.focus = { key, color };
  if (changed) {
    setHighlight(key, color);
    S.glow.color.set(color);
    S.userMoved = false;
    flyTo(COMP[key].cam, COMP[key].tgt, 1.8);
  }
}

export function clearFocus() {
  if (!S || !S.focus) return;
  S.focus = null;
  setHighlight(null);
  S.dirty = true;
  if (!S.userMoved) flyTo(HOME.cam, HOME.tgt, 1.6);
}

export function unmount() {
  if (!S) return;
  cancelAnimationFrame(S.raf);
  S.ro.disconnect(); S.io.disconnect();
  S.controls.dispose();
  S.scene.traverse((o) => {
    if (o.geometry) o.geometry.dispose();
    const mats = Array.isArray(o.material) ? o.material : (o.material ? [o.material] : []);
    for (const m of mats) { if (m.map) m.map.dispose(); m.dispose(); }
  });
  S.envTex.dispose(); S.pmrem.dispose();
  S.renderer.dispose();
  S.renderer.forceContextLoss();
  S.el.innerHTML = '';
  S = null;
}

export const COMPONENTS = COMP;
window.Twin3D = { supported, mount, update, focus, clearFocus, unmount, COMPONENTS: COMP,
  _durum: () => S && { cam: S.camera.position.toArray().map((v) => +v.toFixed(2)), tween: !!S.tween, focus: S.focus } };
window.dispatchEvent(new Event('twin3d-ready'));
