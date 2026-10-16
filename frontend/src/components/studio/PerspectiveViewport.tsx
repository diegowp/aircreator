'use client';

import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { useStudioStore } from '@/store/studioStore';

export const PerspectiveViewport: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { showWireframe, showGrid } = useStudioStore();

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const width = container.clientWidth || 400;
    const height = container.clientHeight || 300;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f1117);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(12, 8, 14);
    camera.lookAt(0, 0, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    container.appendChild(renderer.domElement);

    // Lighting
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 1.2);
    hemiLight.position.set(0, 20, 0);
    scene.add(hemiLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.5);
    dirLight.position.set(10, 20, 10);
    scene.add(dirLight);

    // Ground Grid
    if (showGrid) {
      const grid = new THREE.GridHelper(30, 30, 0x3b82f6, 0x1e293b);
      scene.add(grid);

      const axes = new THREE.AxesHelper(4);
      scene.add(axes);
    }

    // Default reference airplane silhouette / box
    const bodyGeom = new THREE.ConeGeometry(0.8, 6, 16);
    bodyGeom.rotateX(Math.PI / 2);
    const mat = new THREE.MeshStandardMaterial({
      color: 0x94a3b8,
      wireframe: showWireframe,
      roughness: 0.4,
      metalness: 0.2,
    });
    const sampleAircraft = new THREE.Mesh(bodyGeom, mat);
    sampleAircraft.position.set(0, 1.5, 0);
    scene.add(sampleAircraft);

    let animId: number;
    let angle = 0;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      angle += 0.005;
      camera.position.x = Math.sin(angle) * 16;
      camera.position.z = Math.cos(angle) * 16;
      camera.lookAt(0, 1.5, 0);
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!container) return;
      const nw = container.clientWidth;
      const nh = container.clientHeight;
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, nh);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animId);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [showWireframe, showGrid]);

  return (
    <div className="relative w-full h-full border border-slate-700 bg-slate-900 overflow-hidden flex flex-col">
      <div className="absolute top-2 left-3 z-10 bg-slate-800/80 backdrop-blur px-2.5 py-1 rounded text-xs font-semibold text-blue-400 border border-slate-700 select-none">
        3D Perspective (Livre)
      </div>
      <div ref={containerRef} className="w-full h-full cursor-grab" />
    </div>
  );
};
