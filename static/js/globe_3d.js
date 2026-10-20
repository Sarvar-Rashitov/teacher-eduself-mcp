/**
 * EduSelf — Interactive 3D Canvas Globe
 * Inspired by Cobe / WebGL spherical projection.
 * Features:
 * - 360° Drag-to-rotate interaction with physics inertia
 * - Continents point mesh with 3D depth-sorting
 * - Glowing atmospheric aura & radial depth
 * - Highlighted educational markers (Tashkent, Samarkand, Tokyo, London, New York)
 */

(function () {
  'use strict';

  // Major Educational Hub Markers (Lat, Lon, Label, PrimaryFlag)
  const MARKERS = [
    { lat: 41.2995, lon: 69.2401, label: "Toshkent", primary: true, size: 5 },
    { lat: 39.6270, lon: 66.9749, label: "Samarqand", primary: true, size: 4 },
    { lat: 51.5074, lon: -0.1278, label: "London", primary: false, size: 3.5 },
    { lat: 40.7128, lon: -74.0060, label: "New York", primary: false, size: 3.5 },
    { lat: 35.6762, lon: 139.6503, label: "Tokyo", primary: false, size: 3.5 },
    { lat: 25.2048, lon: 55.2708, label: "Dubai", primary: false, size: 3.5 },
    { lat: 1.3521, lon: 103.8198, label: "Singapore", primary: false, size: 3 },
  ];

  // Pre-generate continent points grid (Fibonacci Sphere / landmass representation with high density)
  function generateGlobePoints(count = 3200) {
    const points = [];
    const phi = (1 + Math.sqrt(5)) / 2; // Golden ratio
    for (let i = 0; i < count; i++) {
      const theta = 2 * Math.PI * i / phi;
      const y = 1 - (i / (count - 1)) * 2; // y goes from 1 to -1
      const radiusAtY = Math.sqrt(1 - y * y);
      const x = Math.cos(theta) * radiusAtY;
      const z = Math.sin(theta) * radiusAtY;

      // Latitude and longitude from x, y, z
      const lat = Math.asin(y) * (180 / Math.PI);
      const lon = Math.atan2(z, x) * (180 / Math.PI);

      // Enhanced Central Asia / Uzbekistan coordinate boundaries
      const isUzbekistan = (lat >= 36.5 && lat <= 45.8 && lon >= 56.0 && lon <= 73.5);

      // Continents distribution filter
      const isLand = isUzbekistan || (
        (lat > -35 && lat < 37 && lon > -18 && lon < 52) || // Africa
        (lat > 35 && lat < 72 && lon > -10 && lon < 45) ||  // Europe
        (lat > 5 && lat < 75 && lon > 45 && lon < 145) ||   // Asia & Central Asia
        (lat > 15 && lat < 72 && lon > -165 && lon < -55) || // North America
        (lat > -55 && lat < 12 && lon > -82 && lon < -34) || // South America
        (lat > -40 && lat < -10 && lon > 112 && lon < 155)   // Australia
      );

      if (isLand || Math.random() < 0.07) {
        points.push({ lat, lon, isLand, isUzbekistan });
      }
    }

    // Add extra dense points specifically over Uzbekistan & Silk Road heartland
    for (let j = 0; j < 140; j++) {
      const uLat = 37.2 + Math.random() * 8.2;
      const uLon = 56.8 + Math.random() * 16.2;
      points.push({ lat: uLat, lon: uLon, isLand: true, isUzbekistan: true });
    }

    return points;
  }

  class Interactive3DGlobe {
    constructor(canvasElement, options = {}) {
      this.canvas = canvasElement;
      this.ctx = canvasElement.getContext('2d');
      this.options = Object.assign({
        autoRotateSpeed: 0.0035,
        theta: 0.32, // tilt angle (radians)
        baseRadius: 180,
        primaryColor: '#FF7527',
        landColor: '#64748B',
        oceanGlow: 'rgba(255, 117, 39, 0.08)'
      }, options);

      this.phi = 0.8; // rotation around Y axis
      this.targetPhi = 0.8;
      this.velocity = 0;
      this.isDragging = false;
      this.lastMouseX = 0;
      this.points = generateGlobePoints(3200);
      this.animId = null;

      this.init();
    }

    init() {
      this.handleResize();
      window.addEventListener('resize', () => this.handleResize());
      this.bindEvents();
      this.animate();
    }

    handleResize() {
      const rect = this.canvas.parentElement ? this.canvas.parentElement.getBoundingClientRect() : { width: 1000, height: 1000 };
      const size = Math.min(rect.width || 1000, rect.height || 1000, 1100);
      const dpr = Math.min(window.devicePixelRatio || 1, 2);

      this.canvas.width = size * dpr;
      this.canvas.height = size * dpr;
      this.canvas.style.width = `${size}px`;
      this.canvas.style.height = `${size}px`;

      this.ctx.scale(dpr, dpr);
      this.size = size;
      this.radius = (size / 2) * 0.84;
      this.cx = size / 2;
      this.cy = size / 2;
    }

    bindEvents() {
      const onPointerDown = (clientX) => {
        this.isDragging = true;
        this.lastMouseX = clientX;
        this.velocity = 0;
        this.canvas.style.cursor = 'grabbing';
      };

      const onPointerMove = (clientX) => {
        if (!this.isDragging) return;
        const delta = clientX - this.lastMouseX;
        this.lastMouseX = clientX;
        this.velocity = delta * 0.005;
        this.phi += this.velocity;
      };

      const onPointerUp = () => {
        this.isDragging = false;
        this.canvas.style.cursor = 'grab';
      };

      // Mouse Events
      this.canvas.addEventListener('mousedown', (e) => onPointerDown(e.clientX));
      window.addEventListener('mousemove', (e) => onPointerMove(e.clientX));
      window.addEventListener('mouseup', onPointerUp);

      // Touch Events
      this.canvas.addEventListener('touchstart', (e) => {
        if (e.touches[0]) onPointerDown(e.touches[0].clientX);
      }, { passive: true });
      window.addEventListener('touchmove', (e) => {
        if (e.touches[0]) onPointerMove(e.touches[0].clientX);
      }, { passive: true });
      window.addEventListener('touchend', onPointerUp);

      this.canvas.style.cursor = 'grab';
    }

    project(latDeg, lonDeg) {
      const lat = (latDeg * Math.PI) / 180;
      const lon = (lonDeg * Math.PI) / 180 + this.phi;
      const theta = this.options.theta;

      // 3D Spherical coordinates
      const x = this.radius * Math.cos(lat) * Math.sin(lon);
      const y = this.radius * (Math.sin(lat) * Math.cos(theta) - Math.cos(lat) * Math.cos(lon) * Math.sin(theta));
      const z = this.radius * (Math.sin(lat) * Math.sin(theta) + Math.cos(lat) * Math.cos(lon) * Math.cos(theta));

      return {
        x: this.cx + x,
        y: this.cy - y,
        z: z,
        visible: z > 0 // Front-facing hemisphere
      };
    }

    render() {
      const ctx = this.ctx;
      const cx = this.cx;
      const cy = this.cy;
      const r = this.radius;

      ctx.clearRect(0, 0, this.size, this.size);

      // 1. Atmosphere Outer Glow
      const glowGrad = ctx.createRadialGradient(cx, cy, r * 0.7, cx, cy, r * 1.25);
      glowGrad.addColorStop(0, 'rgba(255, 117, 39, 0.06)');
      glowGrad.addColorStop(0.7, 'rgba(0, 163, 255, 0.08)');
      glowGrad.addColorStop(1, 'rgba(255, 255, 255, 0)');
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, r * 1.25, 0, Math.PI * 2);
      ctx.fill();

      // 2. Sphere Base / Background (Soft Glassy Globe)
      const sphereGrad = ctx.createRadialGradient(cx - r * 0.35, cy - r * 0.35, r * 0.1, cx, cy, r);
      sphereGrad.addColorStop(0, '#FFFFFF');
      sphereGrad.addColorStop(0.75, '#FFF7F2');
      sphereGrad.addColorStop(1, '#FFE9DC');
      ctx.fillStyle = sphereGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();

      // Sphere border ring
      ctx.strokeStyle = 'rgba(255, 117, 39, 0.25)';
      ctx.lineWidth = 2;
      ctx.stroke();

      // 3. Render Continent Points
      for (let i = 0; i < this.points.length; i++) {
        const pt = this.points[i];
        const proj = this.project(pt.lat, pt.lon);
        if (!proj.visible) continue;

        // Depth scale and alpha based on z
        const depthRatio = Math.max(0.2, proj.z / r);
        const pointSize = pt.isUzbekistan ? (2.4 * depthRatio) : (pt.isLand ? (1.7 * depthRatio) : (1.0 * depthRatio));

        if (pt.isUzbekistan) {
          ctx.fillStyle = `rgba(255, 117, 39, ${0.75 + depthRatio * 0.25})`;
        } else if (pt.isLand) {
          ctx.fillStyle = `rgba(80, 95, 115, ${0.4 + depthRatio * 0.55})`;
        } else {
          ctx.fillStyle = `rgba(203, 213, 225, ${0.12 + depthRatio * 0.18})`;
        }

        ctx.beginPath();
        ctx.arc(proj.x, proj.y, pointSize, 0, Math.PI * 2);
        ctx.fill();
      }

      // 4. Render Educational Markers
      const now = Date.now();
      const pulse = Math.sin(now / 250) * 0.5 + 0.5;

      for (let i = 0; i < MARKERS.length; i++) {
        const m = MARKERS[i];
        const proj = this.project(m.lat, m.lon);
        if (!proj.visible) continue;

        const depthRatio = Math.max(0.3, proj.z / r);

        if (m.primary) {
          // Primary Hub: Tashkent & Samarkand (Uzbekistan)
          // Pulsing Beacon Rings
          ctx.strokeStyle = `rgba(255, 117, 39, ${0.4 - pulse * 0.3})`;
          ctx.lineWidth = 1.5;
          ctx.beginPath();
          ctx.arc(proj.x, proj.y, (m.size + 4 + pulse * 6) * depthRatio, 0, Math.PI * 2);
          ctx.stroke();

          // Outer Gold Ring
          ctx.fillStyle = '#FF7527';
          ctx.beginPath();
          ctx.arc(proj.x, proj.y, (m.size + 1.5) * depthRatio, 0, Math.PI * 2);
          ctx.fill();

          // Inner Bright Core
          ctx.fillStyle = '#FFFFFF';
          ctx.beginPath();
          ctx.arc(proj.x, proj.y, (m.size * 0.6) * depthRatio, 0, Math.PI * 2);
          ctx.fill();

          // Label
          if (depthRatio > 0.5) {
            ctx.font = `bold ${Math.round(10 * depthRatio + 1)}px 'Plus Jakarta Sans', sans-serif`;
            ctx.fillStyle = '#1E1E24';
            ctx.shadowColor = 'rgba(255, 255, 255, 0.9)';
            ctx.shadowBlur = 4;
            ctx.fillText(m.label, proj.x + 8 * depthRatio, proj.y + 4 * depthRatio);
            ctx.shadowBlur = 0;
          }
        } else {
          // Secondary World Hubs
          ctx.fillStyle = `rgba(0, 163, 255, ${0.6 + depthRatio * 0.3})`;
          ctx.beginPath();
          ctx.arc(proj.x, proj.y, m.size * depthRatio, 0, Math.PI * 2);
          ctx.fill();

          ctx.fillStyle = '#FFFFFF';
          ctx.beginPath();
          ctx.arc(proj.x, proj.y, (m.size * 0.4) * depthRatio, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }

    animate() {
      if (!this.isDragging) {
        // Natural auto-rotation with momentum dampening
        if (Math.abs(this.velocity) > 0.0001) {
          this.phi += this.velocity;
          this.velocity *= 0.94; // friction
        } else {
          this.phi += this.options.autoRotateSpeed;
        }
      }

      this.render();
      this.animId = requestAnimationFrame(() => this.animate());
    }

    destroy() {
      if (this.animId) cancelAnimationFrame(this.animId);
    }
  }

  // Global initialization hook
  window.Interactive3DGlobe = Interactive3DGlobe;

  document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('globeInteractiveCanvas');
    if (canvas) {
      window.activeGlobe = new Interactive3DGlobe(canvas);
    }
  });
})();
