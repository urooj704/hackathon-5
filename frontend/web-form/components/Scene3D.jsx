'use client';
import { useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function Scene3D() {
  const mountRef = useRef(null);

  useEffect(() => {
    const el = mountRef.current;
    if (!el) return;

    // ── Renderer (performance optimised) ──────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, powerPreference: 'high-performance' });
    renderer.setPixelRatio(1);                          // force 1× — biggest speed win
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.setClearColor(0x000000, 0);
    el.appendChild(renderer.domElement);

    // ── Scene & Camera ────────────────────────────────────
    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, el.clientWidth / el.clientHeight, 0.1, 80);
    camera.position.z = 7;

    // ── Lights ────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0x111133, 3));
    const lA = new THREE.PointLight(0x6366f1, 8, 18);  lA.position.set(5, 5, 4);   scene.add(lA);
    const lB = new THREE.PointLight(0xa855f7, 6, 18);  lB.position.set(-5, -4, 3);  scene.add(lB);
    const lC = new THREE.PointLight(0x22d3ee, 4, 14);  lC.position.set(0, -5, -4);  scene.add(lC);

    // ─────────────────────────────────────────────────────
    //   NEURAL NETWORK SPHERE
    //   Nodes on a sphere surface, connected by glowing lines
    // ─────────────────────────────────────────────────────
    const RADIUS   = 2.4;
    const NODE_CNT = 70;

    const mainGroup = new THREE.Group();
    scene.add(mainGroup);

    // -- Outer ghost sphere (subtle) ----------------------
    const ghostGeo = new THREE.SphereGeometry(RADIUS, 32, 32);
    const ghostMat = new THREE.MeshPhongMaterial({
      color: 0x4f46e5, transparent: true, opacity: 0.04,
      side: THREE.FrontSide, shininess: 0,
    });
    mainGroup.add(new THREE.Mesh(ghostGeo, ghostMat));

    // Wireframe shell
    const shellGeo = new THREE.IcosahedronGeometry(RADIUS, 2);
    const shellMat = new THREE.MeshBasicMaterial({
      color: 0x4f46e5, wireframe: true, transparent: true, opacity: 0.06,
    });
    mainGroup.add(new THREE.Mesh(shellGeo, shellMat));

    // -- Fibonacci nodes on sphere surface ----------------
    const nodePositions = [];
    const golden = Math.PI * (1 + Math.sqrt(5));

    for (let i = 0; i < NODE_CNT; i++) {
      const t   = Math.acos(1 - 2 * (i + 0.5) / NODE_CNT);
      const phi = golden * i;
      nodePositions.push(new THREE.Vector3(
        RADIUS * Math.sin(t) * Math.cos(phi),
        RADIUS * Math.sin(t) * Math.sin(phi),
        RADIUS * Math.cos(t),
      ));
    }

    // Node meshes
    const nodeColors = [0x818cf8, 0xa5b4fc, 0x22d3ee, 0xc084fc, 0x67e8f9];
    const nodeGeo    = new THREE.SphereGeometry(0.045, 8, 8);
    const nodeMeshes = nodePositions.map((pos, i) => {
      const mat  = new THREE.MeshPhongMaterial({
        color: nodeColors[i % nodeColors.length],
        emissive: nodeColors[i % nodeColors.length],
        emissiveIntensity: 1.2,
        shininess: 60,
      });
      const mesh = new THREE.Mesh(nodeGeo, mat);
      mesh.position.copy(pos);
      mainGroup.add(mesh);
      return mesh;
    });

    // Connection lines (only close pairs)
    const lineGroup = new THREE.Group();
    const MAX_DIST  = 1.9;
    for (let i = 0; i < nodePositions.length; i++) {
      for (let j = i + 1; j < nodePositions.length; j++) {
        const d = nodePositions[i].distanceTo(nodePositions[j]);
        if (d > MAX_DIST) continue;
        const alpha = 0.35 * (1 - d / MAX_DIST);
        const geo   = new THREE.BufferGeometry().setFromPoints([nodePositions[i], nodePositions[j]]);
        const mat   = new THREE.LineBasicMaterial({
          color: 0x6366f1, transparent: true, opacity: alpha,
        });
        lineGroup.add(new THREE.Line(geo, mat));
      }
    }
    mainGroup.add(lineGroup);

    // -- Inner bright core --------------------------------
    const coreGeo = new THREE.SphereGeometry(0.28, 16, 16);
    const coreMat = new THREE.MeshPhongMaterial({
      color: 0x818cf8, emissive: 0x6366f1, emissiveIntensity: 2,
      shininess: 100, transparent: true, opacity: 0.9,
    });
    const core = new THREE.Mesh(coreGeo, coreMat);
    mainGroup.add(core);

    // ── Orbital rings ─────────────────────────────────────
    const mkRing = (r, rot, col, opacity) => {
      const m = new THREE.Mesh(
        new THREE.TorusGeometry(r, 0.012, 6, 120),
        new THREE.MeshBasicMaterial({ color: col, transparent: true, opacity }),
      );
      m.rotation.set(...rot);
      scene.add(m);
      return m;
    };
    const ring1 = mkRing(3.4, [Math.PI/2.2,  0,          0], 0x6366f1, 0.30);
    const ring2 = mkRing(3.9, [Math.PI/3.5,  Math.PI/5,  0], 0xa855f7, 0.20);
    const ring3 = mkRing(4.5, [Math.PI/1.7, -Math.PI/4,  0], 0x22d3ee, 0.12);

    // ── Slim particle field (800 only) ────────────────────
    const P = 800;
    const pPos = new Float32Array(P * 3);
    const pCol = new Float32Array(P * 3);
    const pal  = [new THREE.Color(0x6366f1), new THREE.Color(0xa855f7),
                  new THREE.Color(0x22d3ee), new THREE.Color(0x818cf8)];
    for (let i = 0; i < P; i++) {
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(2 * Math.random() - 1);
      const r  = 5.5 + Math.random() * 3.5;
      pPos[i*3]   = r * Math.sin(ph) * Math.cos(th);
      pPos[i*3+1] = r * Math.sin(ph) * Math.sin(th);
      pPos[i*3+2] = r * Math.cos(ph);
      const c = pal[i % pal.length];
      pCol[i*3] = c.r; pCol[i*3+1] = c.g; pCol[i*3+2] = c.b;
    }
    const pGeo = new THREE.BufferGeometry();
    pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
    pGeo.setAttribute('color',    new THREE.BufferAttribute(pCol, 3));
    const particles = new THREE.Points(pGeo,
      new THREE.PointsMaterial({ size: 0.022, vertexColors: true, transparent: true, opacity: 0.55 }));
    scene.add(particles);

    // ── Mouse (throttled via flag) ────────────────────────
    let mx = 0, my = 0, needsMouse = false;
    const onMouse = (e) => {
      if (needsMouse) return;
      needsMouse = true;
      requestAnimationFrame(() => {
        mx = (e.clientX / window.innerWidth  - 0.5) * 2;
        my = (e.clientY / window.innerHeight - 0.5) * 2;
        needsMouse = false;
      });
    };
    window.addEventListener('mousemove', onMouse, { passive: true });

    // ── Resize ────────────────────────────────────────────
    const onResize = () => {
      camera.aspect = el.clientWidth / el.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener('resize', onResize, { passive: true });

    // ── Animation (frame-skipping for low-end devices) ────
    let raf;
    const clock  = new THREE.Clock();
    let lastTime = 0;

    const animate = (now) => {
      raf = requestAnimationFrame(animate);
      if (now - lastTime < 14) return;          // cap at ~60fps, skip if too soon
      lastTime = now;

      const t = clock.getElapsedTime();

      // Main group slow spin
      mainGroup.rotation.y = t * 0.18;
      mainGroup.rotation.x = t * 0.09;

      // Node pulse (emissive intensity breathe)
      const pulse = 0.9 + 0.5 * Math.sin(t * 1.8);
      nodeMeshes.forEach((m, i) => {
        m.material.emissiveIntensity = pulse * (0.7 + 0.3 * Math.sin(t * 2 + i));
      });

      // Core breathe
      const s = 1 + 0.25 * Math.sin(t * 2.2);
      core.scale.setScalar(s);
      coreMat.emissiveIntensity = 1.5 + Math.sin(t * 2.2) * 0.8;

      // Rings
      ring1.rotation.z = t * 0.14;
      ring2.rotation.y = t * 0.10;
      ring3.rotation.x = t * 0.07;

      // Lights dance
      lA.position.x =  Math.sin(t * 0.5) * 6;
      lA.position.y =  Math.cos(t * 0.4) * 5;
      lB.position.x =  Math.cos(t * 0.6) * 6;
      lB.position.z =  Math.sin(t * 0.5) * 5;

      // Particles slow drift
      particles.rotation.y = t * 0.025;

      // Mouse influence
      scene.rotation.y += (mx * 0.28 - scene.rotation.y) * 0.03;
      scene.rotation.x += (-my * 0.18 - scene.rotation.x) * 0.03;

      renderer.render(scene, camera);
    };
    animate(0);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('mousemove', onMouse);
      window.removeEventListener('resize', onResize);
      renderer.dispose();
      if (el.contains(renderer.domElement)) el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={mountRef} style={{ position: 'absolute', inset: 0 }} />;
}
