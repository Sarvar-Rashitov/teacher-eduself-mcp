/**
 * EduSelf — "GlassFolder" 3D Frosted Acrylic Folder Component
 * Interactive category folder with generative domain-warped noise artwork,
 * 3D perspective physics, frosted glass shader, and quiz library filtering.
 */

(function () {
  'use strict';

  // #region Art & Noise Generator
  const ART_PRESETS = {
    eduplay: {
      style: "marble",
      colors: ["#FFF2EB", "#FFB285", "#FF7527", "#E65D0F", "#9A3412", "#431407"],
      scale: 0.65,
      warp: 3.1,
      angle: 0.6,
      gloss: 0.52,
      veins: 0.3,
    },
    physics: {
      style: "streak",
      colors: ["#F0F9FF", "#BAE6FD", "#38BDF8", "#0284C7", "#0C4A6E", "#0369A1"],
      scale: 0.7,
      warp: 1.8,
      angle: -0.45,
      gloss: 0.42,
      veins: 0.15,
    },
    math: {
      style: "marble",
      colors: ["#FAF5FF", "#DDD6FE", "#A78BFA", "#7C3AED", "#4C1D95", "#F59E0B"],
      scale: 0.68,
      warp: 3.4,
      angle: 1.1,
      gloss: 0.55,
      veins: 0.4,
    },
    biology: {
      style: "marble",
      colors: ["#ECFDF5", "#A7F3D0", "#34D399", "#10B981", "#065F46", "#FBBF24"],
      scale: 0.7,
      warp: 2.9,
      angle: 1.8,
      gloss: 0.45,
      veins: 0.3,
    },
    aurora: {
      style: "streak",
      colors: ["#f4efe9", "#e9c2b8", "#c2433f", "#2a1e2a", "#22395e", "#6f97c2", "#e5edf4"],
      scale: 0.7,
      warp: 1.4,
      angle: -0.62,
      gloss: 0.18,
      veins: 0,
    },
    ember: {
      style: "marble",
      colors: ["#07090c", "#16252c", "#3d5f68", "#1a1416", "#a3201a", "#ef4a2b", "#ff8a5c"],
      scale: 0.62,
      warp: 3.2,
      angle: -0.5,
      gloss: 0.55,
      veins: 0.6,
    },
    dusk: {
      style: "marble",
      colors: ["#120c18", "#3e2850", "#8f6c9c", "#2b1a24", "#b3502f", "#eab08a", "#fbe7d2"],
      scale: 0.75,
      warp: 3.6,
      angle: 0.8,
      gloss: 0.5,
      veins: 0.5,
    },
    glacier: {
      style: "streak",
      colors: ["#f7f8fa", "#d9e2ea", "#9fb4c7", "#e8edf2", "#bccbd8", "#ffffff"],
      scale: 0.7,
      warp: 1.6,
      angle: 0.35,
      gloss: 0.25,
      veins: 0,
    },
    verdant: {
      style: "marble",
      colors: ["#070b08", "#173024", "#4f7a5a", "#141812", "#a7843a", "#e9cf87", "#fbf3d6"],
      scale: 0.7,
      warp: 3.4,
      angle: 2.1,
      gloss: 0.5,
      veins: 0.5,
    },
  };

  function hexToRgb(hex) {
    let h = hex.trim().replace(/^#/, "");
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    const n = /^[0-9a-f]{6}$/i.test(h) ? parseInt(h, 16) : 0x808080;
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function rng(seed) {
    let a = seed >>> 0;
    return () => {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function hashString(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
    return h >>> 0;
  }

  function makeFbm(seed) {
    const r = rng(seed);
    const perm = new Uint8Array(512);
    const grad = new Float32Array(512);
    const p = [];
    for (let i = 0; i < 256; i++) p.push(i);
    for (let i = 255; i > 0; i--) {
      const j = Math.floor(r() * (i + 1));
      const t = p[i];
      p[i] = p[j];
      p[j] = t;
    }
    for (let i = 0; i < 512; i++) perm[i] = p[i & 255];
    for (let i = 0; i < 256; i++) {
      const a = r() * Math.PI * 2;
      grad[i * 2] = Math.cos(a);
      grad[i * 2 + 1] = Math.sin(a);
    }
    const noise = (x, y) => {
      const xi = Math.floor(x);
      const yi = Math.floor(y);
      const xf = x - xi;
      const yf = y - yi;
      const X = xi & 255;
      const Y = yi & 255;
      const h00 = perm[X + perm[Y]] * 2;
      const h10 = perm[X + 1 + perm[Y]] * 2;
      const h01 = perm[X + perm[Y + 1]] * 2;
      const h11 = perm[X + 1 + perm[Y + 1]] * 2;
      const d00 = grad[h00] * xf + grad[h00 + 1] * yf;
      const d10 = grad[h10] * (xf - 1) + grad[h10 + 1] * yf;
      const d01 = grad[h01] * xf + grad[h01 + 1] * (yf - 1);
      const d11 = grad[h11] * (xf - 1) + grad[h11 + 1] * (yf - 1);
      const u = xf * xf * xf * (xf * (xf * 6 - 15) + 10);
      const v = yf * yf * yf * (yf * (yf * 6 - 15) + 10);
      return d00 + u * (d10 - d00) + v * (d01 - d00 + u * (d11 - d01 - d10 + d00));
    };
    return (x, y, octaves) => {
      let sum = 0;
      let amp = 0.5;
      for (let i = 0; i < octaves; i++) {
        sum += amp * noise(x, y);
        const nx = 1.6 * x + 1.2 * y + 7.1;
        y = -1.2 * x + 1.6 * y + 3.3;
        x = nx;
        amp *= 0.5;
      }
      return sum;
    };
  }

  function createArtJob(width, height, recipe, seed) {
    const w = Math.max(1, Math.round(width));
    const h = Math.max(1, Math.round(height));
    const colors = recipe.colors && recipe.colors.length >= 2 ? recipe.colors : ["#FFF2EB", "#FF7527"];
    const stops = colors.map((c, i) => ({ t: i / (colors.length - 1), c: hexToRgb(c) }));
    const scale = recipe.scale ?? 0.7;
    const warp = recipe.warp ?? 3;
    const gloss = recipe.gloss ?? 0.45;
    const veins = recipe.veins ?? 0.2;
    const streak = recipe.style === "streak";
    const fbm = makeFbm(seed * 977 + 13);
    const r = rng(seed + 1);
    const ox = r() * 50;
    const oy = r() * 50;
    const angle = (recipe.angle ?? 0) + (r() - 0.5) * 0.5;
    const ca = Math.cos(angle);
    const sa = Math.sin(angle);
    const m = Math.min(w, h);
    const gw = Math.ceil(w / 2) + 3;
    const gh = Math.ceil(h / 2) + 3;
    const G = new Float32Array(gw * gh);
    const GQ = new Float32Array(gw * gh);
    const F = new Float32Array(w * h);
    const Q = new Float32Array(w * h);
    const pixels = new Uint8ClampedArray(w * h * 4);
    let row = 0;

    const field = (gy) => {
      for (let gx = 0; gx < gw; gx++) {
        const u = ((gx - 1) * 2 - w / 2) / m;
        const v = ((gy - 1) * 2 - h / 2) / m;
        let px = (u * ca - v * sa) * scale;
        let py = (u * sa + v * ca) * scale;
        if (streak) {
          px *= 0.14;
          py *= 2.2;
        }
        px += ox;
        py += oy;
        const qx = fbm(px, py, 3);
        const qy = fbm(px + 5.2, py + 1.3, 3);
        const rx = fbm(px + warp * qx + 1.7, py + warp * qy + 9.2, 3);
        const ry = fbm(px + warp * qx + 8.3, py + warp * qy + 2.8, 3);
        G[gy * gw + gx] = fbm(px + warp * rx, py + warp * ry, 4);
        GQ[gy * gw + gx] = Math.sqrt(qx * qx + qy * qy);
      }
    };

    const upsample = () => {
      const cr = (a, b, c, d) => (-a + 9 * b + 9 * c - d) / 16;
      const T = new Float32Array(w * gh);
      for (let gy = 0; gy < gh; gy++) {
        const r = gy * gw;
        for (let x = 0; x < w; x++) {
          const c = (x >> 1) + 1;
          T[gy * w + x] = x & 1 ? cr(G[r + c - 1], G[r + c], G[r + c + 1], G[r + c + 2]) : G[r + c];
        }
      }
      for (let y = 0; y < h; y++) {
        const c = (y >> 1) + 1;
        for (let x = 0; x < w; x++) {
          F[y * w + x] =
            y & 1 ? cr(T[(c - 1) * w + x], T[c * w + x], T[(c + 1) * w + x], T[(c + 2) * w + x]) : T[c * w + x];
          const gx = (x >> 1) + 1;
          const q0 = GQ[c * gw + gx];
          const qx = x & 1 ? (q0 + GQ[c * gw + gx + 1]) / 2 : q0;
          const q1 = y & 1 ? (x & 1 ? (GQ[(c + 1) * gw + gx] + GQ[(c + 1) * gw + gx + 1]) / 2 : GQ[(c + 1) * gw + gx]) : qx;
          Q[y * w + x] = (qx + q1) / 2;
        }
      }
    };

    const colorize = () => {
      const sample = [];
      const stride = Math.max(1, Math.floor(F.length / 4096));
      for (let i = 0; i < F.length; i += stride) sample.push(F[i]);
      sample.sort((a, b) => a - b);
      const lo = sample[Math.floor(sample.length * 0.02)];
      const hi = sample[Math.floor(sample.length * 0.98)];
      const k = 1 / (hi - lo || 1);
      const lx = -0.55;
      const ly = -0.65;
      const lz = 0.52;
      const slope = k * m * 0.012;
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const i = y * w + x;
          let t = (F[i] - lo) * k;
          t = t < 0 ? 0 : t > 1 ? 1 : t;
          let j = 1;
          while (j < stops.length - 1 && stops[j].t < t) j++;
          const a = stops[j - 1];
          const b = stops[j];
          let f = (t - a.t) / (b.t - a.t || 1);
          f = f < 0 ? 0 : f > 1 ? 1 : f;
          f = f * f * (3 - 2 * f);
          const gx = (F[x < w - 1 ? i + 1 : i] - F[x > 0 ? i - 1 : i]) * slope;
          const gy = (F[y < h - 1 ? i + w : i] - F[y > 0 ? i - w : i]) * slope;
          const nd = (-gx * lx - gy * ly + lz) / Math.sqrt(gx * gx + gy * gy + 1);
          const spec = Math.pow(nd > 0 ? nd : 0, 24) * gloss * 255;
          const silk = 1 + 0.035 * Math.sin(t * 150 + Q[i] * 24);
          const vein = veins * Math.max(0, 1 - Math.abs(Q[i] - 0.42) * 14) * 0.6;
          const lit = (0.82 + 0.28 * nd) * silk * (1 - vein);
          pixels[i * 4] = (a.c[0] + (b.c[0] - a.c[0]) * f) * lit + spec;
          pixels[i * 4 + 1] = (a.c[1] + (b.c[1] - a.c[1]) * f) * lit + spec;
          pixels[i * 4 + 2] = (a.c[2] + (b.c[2] - a.c[2]) * f) * lit + spec;
          pixels[i * 4 + 3] = 255;
        }
      }
    };

    const step = (rows) => {
      if (row >= gh) return true;
      const end = Math.min(gh, row + Math.max(1, rows));
      while (row < end) field(row++);
      if (row < gh) return false;
      upsample();
      colorize();
      return true;
    };

    return { width: w, height: h, pixels, step };
  }

  const artCache = new Map();
  const queue = [];
  let pumping = false;

  function pump() {
    if (pumping) return;
    pumping = true;
    const tick = () => {
      const until = performance.now() + 7;
      while (queue.length && performance.now() < until) {
        const head = queue[0];
        if (head.job.step(4)) {
          queue.shift();
          const c = document.createElement("canvas");
          c.width = head.job.width;
          c.height = head.job.height;
          c.getContext("2d")?.putImageData(new ImageData(head.job.pixels, c.width, c.height), 0, 0);
          head.done(c);
        }
      }
      if (queue.length) requestAnimationFrame(tick);
      else pumping = false;
    };
    requestAnimationFrame(tick);
  }

  function paintArt(recipe, seed, w, h, priority) {
    const key = JSON.stringify([recipe, seed, w, h]);
    let p = artCache.get(key);
    if (!p) {
      p = new Promise((done) => {
        let at = queue.length;
        while (at > 1 && queue[at - 1].priority > priority) at--;
        queue.splice(at, 0, { job: createArtJob(w, h, recipe, seed), priority, done });
        pump();
      });
      artCache.set(key, p);
    }
    return p;
  }

  function fanSlot(index, count) {
    return count <= 1 ? 0 : (index / (count - 1)) * 2 - 1;
  }
  // #endregion

  // Geometry Constants
  const W = 340;
  const H = 272;
  const HEADROOM = 54;
  const FRONT_TOP = 74;
  const FRONT_H = H - FRONT_TOP;
  const SHEET_W = 272;
  const SHEET_H = 184;

  const BACK_PATH =
    "M0 56A22 22 0 0 1 22 34L146 34C170 34 172 0 198 0L318 0A22 22 0 0 1 340 22L340 250A22 22 0 0 1 318 272L22 272A22 22 0 0 1 0 250Z";
  const FRONT_PATH =
    "M0 22A22 22 0 0 1 22 0L118 0C144 0 146 32 172 32L318 32A22 22 0 0 1 340 54L340 " +
    (FRONT_H - 22) +
    "A22 22 0 0 1 318 " +
    FRONT_H +
    "L22 " +
    FRONT_H +
    "A22 22 0 0 1 0 " +
    (FRONT_H - 22) +
    "Z";

  class GlassFolderWidget {
    constructor(container, options = {}) {
      this.container = container;
      this.options = Object.assign(
        {
          label: "Fanlar Kutubxonasi",
          meta: null,
          tone: "light",
          art: "eduplay",
          seed: 5,
          width: 340,
          action: "more",
          open: false,
          files: [
            { name: "Umumiy", meta: "Barcha testlar", art: "eduplay" },
            { name: "Fizika", meta: "Zichlik, Massa", art: "physics" },
            { name: "Matematika", meta: "Kasrlar, Algebra", art: "math" },
            { name: "Informatika", meta: "AI, Algoritm", art: "aurora" },
            { name: "Biologiya", meta: "Hujayra, Tabiat", art: "biology" },
          ],
          menu: [
            { label: "Barcha viktorinalarni ko‘rish", action: "view_all" },
            { label: "Yangi fan qo‘shish", action: "new_subject" },
          ],
          onFileSelect: null,
          onOpenChange: null,
        },
        options
      );

      this.isOpen = !!this.options.open;
      this.menuOpen = false;
      this.selectedSubject = "all";
      this.init();
    }

    init() {
      const { width, tone, label, art, seed, files, action } = this.options;
      const k = width / W;
      const uid = 'gf_' + Math.random().toString(36).substring(2, 9);
      this.uid = uid;
      this.k = k;

      this.container.classList.add('gf-root');
      this.container.setAttribute('data-tone', tone);
      this.container.setAttribute('data-place', 'bottom-left');
      if (this.isOpen) this.container.setAttribute('data-open', 'true');
      this.container.setAttribute('data-entered', 'true');
      this.container.style.width = width + 'px';
      this.container.style.height = (H + HEADROOM) * k + 'px';

      // 1. Stage Wrapper
      const stage = document.createElement('div');
      stage.className = 'gf-stage';
      stage.style.transform = `translateY(${HEADROOM * k}px) scale(${k})`;

      // 2. 3D Tilt Wrapper
      const tilt = document.createElement('div');
      tilt.className = 'gf-tilt';

      // Soft Shadow
      const shadow = document.createElement('div');
      shadow.className = 'gf-shadow';
      tilt.appendChild(shadow);

      // Back Panel with Art
      const back = document.createElement('div');
      back.className = 'gf-back';
      back.style.clipPath = `path('${BACK_PATH}')`;
      
      const backCanvas = document.createElement('canvas');
      backCanvas.className = 'gf-art';
      backCanvas.width = W + 24;
      backCanvas.height = H + 24;
      back.appendChild(backCanvas);

      const sheen = document.createElement('div');
      sheen.className = 'gf-back-sheen';
      back.appendChild(sheen);
      tilt.appendChild(back);

      // Paint Back Artwork
      const recipe = ART_PRESETS[art] || ART_PRESETS.eduplay;
      paintArt(recipe, seed, W + 24, H + 24, 0).then((c) => {
        const ctx = backCanvas.getContext('2d');
        if (ctx) ctx.drawImage(c, 0, 0);
        backCanvas.setAttribute('data-ready', 'true');
      });

      // Back Rim
      const backRim = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      backRim.setAttribute('class', 'gf-rim gf-back-rim');
      backRim.setAttribute('viewBox', `0 0 ${W} ${H}`);
      backRim.innerHTML = `<path d="${BACK_PATH}" />`;
      tilt.appendChild(backRim);

      // Files Container (Between back and front glass)
      const filesWrap = document.createElement('div');
      filesWrap.className = 'gf-files';
      filesWrap.setAttribute('role', 'list');
      filesWrap.setAttribute('aria-label', label + ' tarkibi');
      this.filesWrap = filesWrap;

      this.renderFiles(filesWrap, files);
      tilt.appendChild(filesWrap);

      // Front Frosted Glass Panel
      const front = document.createElement('div');
      front.className = 'gf-front';
      front.style.clipPath = `path('${FRONT_PATH}')`;

      const tint = document.createElement('div');
      tint.className = 'gf-tint';
      front.appendChild(tint);

      const spec = document.createElement('div');
      spec.className = 'gf-spec';
      front.appendChild(spec);

      // Front Rim SVG
      const frontRim = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      frontRim.setAttribute('class', 'gf-rim gf-front-rim');
      frontRim.setAttribute('viewBox', `0 0 ${W} ${FRONT_H}`);
      frontRim.innerHTML = `
        <defs>
          <linearGradient id="gf-rim-${uid}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#fff" stop-opacity="0.95" />
            <stop offset="0.35" stop-color="#fff" stop-opacity="0.45" />
            <stop offset="1" stop-color="#FF7527" stop-opacity="0.25" />
          </linearGradient>
        </defs>
        <path d="${FRONT_PATH}" stroke="url(#gf-rim-${uid})" />
      `;
      front.appendChild(frontRim);

      // Main Clickable Hit Area
      const hitBtn = document.createElement('button');
      hitBtn.type = 'button';
      hitBtn.className = 'gf-hit';
      hitBtn.setAttribute('aria-expanded', String(this.isOpen));
      hitBtn.setAttribute('aria-label', (this.isOpen ? "Yopish " : "Ochish ") + label);
      hitBtn.addEventListener('click', () => {
        this.toggleOpen();
      });
      front.appendChild(hitBtn);
      this.hitBtn = hitBtn;

      // Label Group
      const labelDiv = document.createElement('div');
      labelDiv.className = 'gf-label';
      const metaText = this.options.meta || (files.length + ' ta fan');
      labelDiv.innerHTML = `
        <span class="gf-title">${this.options.label}</span>
        <span class="gf-meta">${metaText}</span>
      `;
      front.appendChild(labelDiv);
      this.labelEl = labelDiv.querySelector('.gf-title');
      this.metaEl = labelDiv.querySelector('.gf-meta');

      tilt.appendChild(front);

      // Action Button (+ or ···)
      if (action !== 'none') {
        const keyBtn = document.createElement('button');
        keyBtn.type = 'button';
        keyBtn.className = 'gf-key gf-key--' + action;
        keyBtn.setAttribute('aria-label', action === 'add' ? 'Yangi fan' : 'Ko‘proq amallar');
        if (action === 'add') {
          keyBtn.innerHTML = `
            <svg class="gf-glyph gf-glyph--plus" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 4.5v15M4.5 12h15" />
            </svg>
          `;
          keyBtn.addEventListener('click', () => {
            if (window.eduAudio) window.eduAudio.playCoin();
            window.location.href = '/editor/new/';
          });
        } else {
          keyBtn.innerHTML = `
            <svg class="gf-glyph gf-glyph--more" viewBox="0 0 30 12" aria-hidden="true">
              <rect x="1" y="1.5" width="8" height="9" rx="3.4" />
              <rect x="11" y="1.5" width="8" height="9" rx="3.4" />
              <rect x="21" y="1.5" width="8" height="9" rx="3.4" />
            </svg>
          `;
          keyBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleMenu();
          });
        }
        tilt.appendChild(keyBtn);
        this.keyBtn = keyBtn;

        // Context Menu
        const menuEl = document.createElement('div');
        menuEl.className = 'gf-menu';
        menuEl.id = 'gf-menu-' + uid;
        menuEl.setAttribute('role', 'menu');

        const menuItems = [
          { label: this.isOpen ? "Papkani yopish" : "Papkani ochish", action: "toggle_open" },
          { label: "Barcha testlarni ko‘rish", action: "view_all" },
          { label: "Yangi viktorina tuzish", action: "new_quiz" },
        ];

        menuItems.forEach((item) => {
          const mBtn = document.createElement('button');
          mBtn.type = 'button';
          mBtn.role = 'menuitem';
          mBtn.className = 'gf-menu-item';
          mBtn.textContent = item.label;
          mBtn.addEventListener('click', () => {
            this.closeMenu();
            if (item.action === 'toggle_open') {
              this.toggleOpen();
            } else if (item.action === 'view_all') {
              this.selectSubject('Umumiy');
            } else if (item.action === 'new_quiz') {
              window.location.href = '/editor/new/';
            }
          });
          menuEl.appendChild(mBtn);
        });

        tilt.appendChild(menuEl);
        this.menuEl = menuEl;
      }

      stage.appendChild(tilt);
      this.container.appendChild(stage);

      // Mouse Parallax Follow
      this.setupPointerPhysics(this.container);

      // Outside click to close menu
      document.addEventListener('pointerdown', (e) => {
        if (this.menuOpen && !this.menuEl.contains(e.target) && !this.keyBtn.contains(e.target)) {
          this.closeMenu();
        }
      });
    }

    renderFiles(filesWrap, files) {
      filesWrap.innerHTML = '';
      const maxVisible = 5;
      const start = Math.max(0, files.length - maxVisible);
      const visible = files.slice(start);

      visible.forEach((file, v) => {
        const slot = fanSlot(v, visible.length);
        const fileSeed = hashString(file.name);
        const jRng = rng(fileSeed);
        const jx = ((jRng() - 0.5) * 10).toFixed(2);
        const jr = ((jRng() - 0.5) * 3.2).toFixed(2);
        const depth = visible.length - 1 - v;

        const slotEl = document.createElement('div');
        slotEl.className = 'gf-sheet-slot';
        slotEl.setAttribute('role', 'listitem');

        const sheet = document.createElement('button');
        sheet.type = 'button';
        sheet.className = 'gf-sheet gf-sheet--art';
        sheet.style.setProperty('--gf-slot', slot);
        sheet.style.setProperty('--gf-depth', depth);
        sheet.style.setProperty('--gf-jx', `${jx}px`);
        sheet.style.setProperty('--gf-jr', `${jr}deg`);
        sheet.style.zIndex = v + 1;

        // Canvas artwork inside sheet
        const sheetCanvas = document.createElement('canvas');
        sheetCanvas.className = 'gf-sheet-art';
        sheetCanvas.width = SHEET_W;
        sheetCanvas.height = SHEET_H;
        sheet.appendChild(sheetCanvas);

        const recipe = ART_PRESETS[file.art] || ART_PRESETS.eduplay;
        paintArt(recipe, fileSeed % 997, SHEET_W, SHEET_H, 1).then((c) => {
          const ctx = sheetCanvas.getContext('2d');
          if (ctx) ctx.drawImage(c, 0, 0);
          sheetCanvas.setAttribute('data-ready', 'true');
        });

        // Sheet Header Info
        const head = document.createElement('span');
        head.className = 'gf-sheet-head';
        head.innerHTML = `
          <span class="gf-sheet-name">${file.name}</span>
          ${file.meta ? `<span class="gf-sheet-meta">${file.meta}</span>` : ''}
        `;
        sheet.appendChild(head);

        // Click handler
        sheet.addEventListener('click', (e) => {
          e.stopPropagation();
          this.selectSubject(file.name, file);
        });

        sheet.addEventListener('mouseenter', () => {
          if (window.eduAudio) window.eduAudio.playTick();
        });

        slotEl.appendChild(sheet);
        filesWrap.appendChild(slotEl);
      });
    }

    setupPointerPhysics(el) {
      let raf = 0;
      let px = 0;
      let py = 0;

      const write = () => {
        raf = 0;
        el.style.setProperty('--gf-px', px.toFixed(3));
        el.style.setProperty('--gf-py', py.toFixed(3));
      };

      el.addEventListener('pointermove', (e) => {
        if (e.pointerType === 'touch') return;
        const r = el.getBoundingClientRect();
        px = ((e.clientX - r.left) / r.width) * 2 - 1;
        py = ((e.clientY - r.top) / r.height) * 2 - 1;
        if (!raf) raf = requestAnimationFrame(write);
      });

      el.addEventListener('pointerleave', () => {
        px = 0;
        py = 0;
        if (!raf) raf = requestAnimationFrame(write);
      });
    }

    toggleOpen() {
      this.isOpen = !this.isOpen;
      if (this.isOpen) {
        this.container.setAttribute('data-open', 'true');
        this.hitBtn?.setAttribute('aria-expanded', 'true');
        if (window.eduAudio) window.eduAudio.playClick();
      } else {
        this.container.removeAttribute('data-open');
        this.hitBtn?.setAttribute('aria-expanded', 'false');
        if (window.eduAudio) window.eduAudio.playTick();
      }
      if (this.options.onOpenChange) {
        this.options.onOpenChange(this.isOpen);
      }
    }

    toggleMenu() {
      this.menuOpen = !this.menuOpen;
      if (this.menuOpen) {
        this.menuEl?.setAttribute('data-open', 'true');
        this.keyBtn?.setAttribute('aria-expanded', 'true');
      } else {
        this.closeMenu();
      }
    }

    closeMenu() {
      this.menuOpen = false;
      this.menuEl?.removeAttribute('data-open');
      this.keyBtn?.setAttribute('aria-expanded', 'false');
    }

    selectSubject(subjectName, fileObj) {
      if (window.eduAudio) window.eduAudio.playCoin();
      this.selectedSubject = subjectName;

      // Update folder label
      if (this.metaEl) {
        this.metaEl.textContent = `Faol: ${subjectName}`;
      }

      // External callback
      if (this.options.onFileSelect) {
        this.options.onFileSelect(fileObj || { name: subjectName });
      }

      // Trigger global filter in teacher dashboard
      if (window.filterQuizzesBySubject) {
        window.filterQuizzesBySubject(subjectName);
      }
    }
  }

  window.GlassFolderWidget = GlassFolderWidget;

  // Auto-init on DOMContentLoaded for elements with [data-glass-folder]
  document.addEventListener('DOMContentLoaded', () => {
    const el = document.getElementById('teacherGlassFolderContainer');
    if (el) {
      // Gather subjects from data attributes or DOM
      let filesData = null;
      try {
        const raw = el.getAttribute('data-files');
        if (raw) filesData = JSON.parse(raw);
      } catch (e) {}

      window.teacherFolderInstance = new GlassFolderWidget(el, {
        label: "Fanlar Bo‘limi",
        meta: "5 ta fan • Barchasi",
        art: "eduplay",
        width: 320,
        open: true, // open by default so files are instantly visible and interactive
        files: filesData || [
          { name: "Umumiy", meta: "Barcha testlar", art: "eduplay" },
          { name: "Fizika", meta: "Zichlik, Massa", art: "physics" },
          { name: "Matematika", meta: "Kasrlar, Algebra", art: "math" },
          { name: "Informatika", meta: "AI, Algoritm", art: "aurora" },
          { name: "Biologiya", meta: "Hujayra, Tabiat", art: "biology" },
        ],
        onFileSelect: (file) => {
          if (window.filterQuizzesBySubject) {
            window.filterQuizzesBySubject(file.name);
          }
        }
      });
    }

    const showcaseEl = document.getElementById('showcaseGlassFolder');
    if (showcaseEl) {
      new GlassFolderWidget(showcaseEl, {
        label: "Dizayn Vitrinasi",
        meta: "5 ta fan • Namunaviy",
        art: "eduplay",
        width: 320,
        open: true,
        files: [
          { name: "Umumiy Fanlar", meta: "Katalog", art: "eduplay" },
          { name: "Fizika & Kosmos", meta: "3D animatsiya", art: "physics" },
          { name: "Matematika", meta: "Fraktal xaritalar", art: "math" },
          { name: "Informatika", meta: "AI Neyrotarmoqlar", art: "aurora" },
          { name: "Biologiya", meta: "Ekotizimlar", art: "biology" },
        ],
      });
    }
  });

})();
