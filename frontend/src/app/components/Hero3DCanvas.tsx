'use client';

import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export default function Hero3DCanvas() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const width = container.clientWidth || 800;
    const height = container.clientHeight || 320;

    // Scene, Camera, Renderer
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, 7);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Group for mouse interaction
    const mainGroup = new THREE.Group();
    scene.add(mainGroup);

    // 1. Floating 9:16 Vertical Phone Hologram
    const phoneWidth = 1.6;
    const phoneHeight = 2.8;
    const phoneDepth = 0.12;
    const phoneGeo = new THREE.BoxGeometry(phoneWidth, phoneHeight, phoneDepth);
    
    // Create animated canvas texture for the phone screen
    const screenCanvas = document.createElement('canvas');
    screenCanvas.width = 512;
    screenCanvas.height = 896;
    const ctx = screenCanvas.getContext('2d');
    const screenTexture = new THREE.CanvasTexture(screenCanvas);

    const phoneMat = new THREE.MeshStandardMaterial({
      color: 0x0a0f1d,
      roughness: 0.2,
      metalness: 0.85,
    });
    const screenMat = new THREE.MeshBasicMaterial({
      map: screenTexture,
      transparent: true,
      opacity: 0.95,
    });

    const materials = [
      phoneMat, phoneMat, phoneMat, phoneMat,
      screenMat, // Front Face
      phoneMat   // Back Face
    ];

    const phoneMesh = new THREE.Mesh(phoneGeo, materials);
    mainGroup.add(phoneMesh);

    // 2. Glowing Neon Rim Border
    const edges = new THREE.EdgesGeometry(phoneGeo);
    const lineMat = new THREE.LineBasicMaterial({
      color: 0xa855f7,
      linewidth: 2,
      transparent: true,
      opacity: 0.8
    });
    const wireframe = new THREE.LineSegments(edges, lineMat);
    mainGroup.add(wireframe);

    // 3. Orbiting Neural Particle Cloud
    const particleCount = 180;
    const particleGeo = new THREE.BufferGeometry();
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);

    for (let i = 0; i < particleCount; i++) {
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos((Math.random() * 2) - 1);
      const r = 2.4 + Math.random() * 1.8;

      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);

      // Gradient color (amber to purple to cyan)
      const mix = Math.random();
      if (mix < 0.33) {
        colors[i * 3] = 0.96; colors[i * 3 + 1] = 0.62; colors[i * 3 + 2] = 0.04; // Amber
      } else if (mix < 0.66) {
        colors[i * 3] = 0.66; colors[i * 3 + 1] = 0.33; colors[i * 3 + 2] = 0.97; // Purple
      } else {
        colors[i * 3] = 0.22; colors[i * 3 + 1] = 0.74; colors[i * 3 + 2] = 0.97; // Cyan
      }
    }

    particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    particleGeo.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const pMat = new THREE.PointsMaterial({
      size: 0.06,
      vertexColors: true,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending
    });
    const particles = new THREE.Points(particleGeo, pMat);
    mainGroup.add(particles);

    // 4. Orbiting Energy Rings
    const ringGeo1 = new THREE.TorusGeometry(2.3, 0.015, 16, 100);
    const ringMat1 = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.5 });
    const ring1 = new THREE.Mesh(ringGeo1, ringMat1);
    ring1.rotation.x = Math.PI / 3;
    mainGroup.add(ring1);

    const ringGeo2 = new THREE.TorusGeometry(2.8, 0.015, 16, 100);
    const ringMat2 = new THREE.MeshBasicMaterial({ color: 0xf43f5e, transparent: true, opacity: 0.4 });
    const ring2 = new THREE.Mesh(ringGeo2, ringMat2);
    ring2.rotation.y = Math.PI / 4;
    ring2.rotation.x = -Math.PI / 6;
    mainGroup.add(ring2);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.7);
    scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xa855f7, 2.5);
    dirLight1.position.set(4, 5, 4);
    scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0x38bdf8, 2.0);
    dirLight2.position.set(-4, -3, 3);
    scene.add(dirLight2);

    // Interactive Mouse Tracking
    let targetRotX = 0;
    let targetRotY = 0;
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;

    const onMouseMove = (e: MouseEvent) => {
      const rect = container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);
      if (!isDragging) {
        targetRotY = x * 0.45;
        targetRotX = -y * 0.35;
      }
    };

    const onMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const onMouseUp = () => {
      isDragging = false;
    };

    const onDragMove = (e: MouseEvent) => {
      if (!isDragging) return;
      const deltaX = e.clientX - prevMouseX;
      const deltaY = e.clientY - prevMouseY;
      targetRotY += deltaX * 0.01;
      targetRotX += deltaY * 0.01;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    container.addEventListener('mousemove', onMouseMove);
    container.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mouseup', onMouseUp);
    window.addEventListener('mousemove', onDragMove);

    // Animation Loop
    let animId: number;
    let clock = new THREE.Clock();
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const elapsedTime = prefersReducedMotion ? 1.0 : clock.getElapsedTime();

      if (!prefersReducedMotion) {
        // Smooth interpolation for mouse tilt
        mainGroup.rotation.y += (targetRotY - mainGroup.rotation.y) * 0.08;
        mainGroup.rotation.x += (targetRotX - mainGroup.rotation.x) * 0.08;

        // Subtle float oscillation
        phoneMesh.position.y = Math.sin(elapsedTime * 1.8) * 0.08;
        wireframe.position.y = phoneMesh.position.y;

        // Rotate particle cloud & rings
        particles.rotation.y = elapsedTime * 0.08;
        particles.rotation.x = elapsedTime * 0.04;
        ring1.rotation.z = elapsedTime * 0.15;
        ring2.rotation.z = -elapsedTime * 0.12;
      } else {
        mainGroup.rotation.y = 0.15;
        mainGroup.rotation.x = 0.05;
        phoneMesh.position.y = 0;
        wireframe.position.y = 0;
      }

      // Update Phone Screen Canvas Texture
      if (ctx) {
        ctx.fillStyle = '#060a14';
        ctx.fillRect(0, 0, 512, 896);

        // Header simulation
        ctx.fillStyle = '#38bdf8';
        ctx.font = 'bold 28px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('⚡ AI CLIPPER 3D', 256, 90);

        // Simulated Face Tracker Box
        const boxPulse = prefersReducedMotion ? 0 : Math.sin(elapsedTime * 3) * 6;
        const boxX = 146 - boxPulse / 2;
        const boxY = 230 - boxPulse / 2;
        const boxW = 220 + boxPulse;
        const boxH = 220 + boxPulse;
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 4;
        ctx.strokeRect(boxX, boxY, boxW, boxH);

        // Label on tracker
        ctx.fillStyle = '#10b981';
        ctx.font = 'bold 18px sans-serif';
        ctx.fillText('SPEAKER 1 [98% CONF]', 256, boxY - 14);

        // Karaoke Subtitle Simulation
        ctx.font = 'bold 36px sans-serif';
        ctx.fillStyle = '#facc15'; // Hormozi Yellow active
        ctx.fillText('VIRAL HOOK', 256, 560);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 26px sans-serif';
        ctx.fillText('THAT GETS 10M VIEWS', 256, 605);

        // Dynamic Audio Spectrum Waveform Bars
        const barCount = 18;
        const barWidth = 16;
        const startX = 60;
        for (let b = 0; b < barCount; b++) {
          const h = prefersReducedMotion ? 40 : 25 + Math.abs(Math.sin(elapsedTime * 4 + b * 0.5)) * 90;
          ctx.fillStyle = b % 2 === 0 ? '#ec4899' : '#8b5cf6';
          ctx.fillRect(startX + b * 22, 790 - h, barWidth, h);
        }

        screenTexture.needsUpdate = true;
      }

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const newW = container.clientWidth;
      const newH = container.clientHeight || 320;
      camera.aspect = newW / newH;
      camera.updateProjectionMatrix();
      renderer.setSize(newW, newH);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      cancelAnimationFrame(animId);
      container.removeEventListener('mousemove', onMouseMove);
      container.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mouseup', onMouseUp);
      window.removeEventListener('mousemove', onDragMove);
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      role="img"
      aria-label="Interactive 3D canvas showcasing 9:16 vertical video with speaker face-tracking and karaoke subtitles"
      className="w-full h-80 relative rounded-2xl overflow-hidden cursor-grab active:cursor-grabbing border border-purple-500/20 bg-gradient-to-b from-purple-950/20 via-slate-900/40 to-slate-950/80 shadow-2xl backdrop-blur-md"
      title="Interactive 3D Hologram: Drag to rotate, move mouse to tilt"
    >
      <div className="absolute top-3 left-4 text-xs font-mono uppercase tracking-widest text-purple-400/80 pointer-events-none flex items-center space-x-2">
        <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping inline-block"></span>
        <span>Interactive 3D Viewport · Drag / Tilt Enabled</span>
      </div>
      <div className="absolute bottom-3 right-4 text-[11px] font-mono text-slate-400 pointer-events-none">
        60 FPS WebGL · Three.js
      </div>
    </div>
  );
}
