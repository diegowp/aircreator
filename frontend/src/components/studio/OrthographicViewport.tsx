'use client';

import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { useStudioStore } from '@/store/studioStore';

interface OrthographicViewportProps {
  title: string;
  plane: 'top' | 'front' | 'side'; // XZ, XY, or ZY
  blueprintUrl?: string;
  aspectWidth?: number;
  aspectHeight?: number;
}

export const OrthographicViewport: React.FC<OrthographicViewportProps> = ({
  title,
  plane,
  blueprintUrl,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const { showGrid, blueprintOpacity } = useStudioStore();

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const width = container.clientWidth || 400;
    const height = container.clientHeight || 300;

    // Three.js Scene, Orthographic Camera, Renderer
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1a1d24);

    const frustumSize = 16; // 16 meters coverage
    const aspect = width / height;
    const camera = new THREE.OrthographicCamera(
      (-frustumSize * aspect) / 2,
      (frustumSize * aspect) / 2,
      frustumSize / 2,
      -frustumSize / 2,
      0.1,
      1000
    );

    // Setup orientation based on projection plane
    if (plane === 'top') {
      // Look from top down (+Y looking towards -Y)
      camera.position.set(0, 50, 0);
      camera.up.set(0, 0, 1); // +Z forward
      camera.lookAt(0, 0, 0);
    } else if (plane === 'front') {
      // Look from front towards tail (+Z looking towards -Z)
      camera.position.set(0, 0, 50);
      camera.up.set(0, 1, 0); // +Y up
      camera.lookAt(0, 0, 0);
    } else if (plane === 'side') {
      // Look from right side (+X looking towards -X)
      camera.position.set(50, 0, 0);
      camera.up.set(0, 1, 0); // +Y up
      camera.lookAt(0, 0, 0);
    }

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Grid helper
    if (showGrid) {
      const grid = new THREE.GridHelper(20, 20, 0x4a5568, 0x2d3748);
      if (plane === 'front') grid.rotation.x = Math.PI / 2;
      if (plane === 'side') grid.rotation.z = Math.PI / 2;
      scene.add(grid);

      // Axes guide
      const axes = new THREE.AxesHelper(3);
      scene.add(axes);
    }

    // Blueprint plane overlay if image provided
    if (blueprintUrl) {
      const loader = new THREE.TextureLoader();
      loader.load(blueprintUrl, (texture) => {
        texture.minFilter = THREE.LinearFilter;
        const geom = new THREE.PlaneGeometry(12, 12);
        const mat = new THREE.MeshBasicMaterial({
          map: texture,
          transparent: true,
          opacity: blueprintOpacity,
          side: THREE.DoubleSide,
        });
        const planeMesh = new THREE.Mesh(geom, mat);
        if (plane === 'top') planeMesh.rotation.x = -Math.PI / 2;
        if (plane === 'side') planeMesh.rotation.y = Math.PI / 2;
        scene.add(planeMesh);
      });
    }

    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      renderer.render(scene, camera);
    };
    animate();

    const handleResize = () => {
      if (!container) return;
      const nw = container.clientWidth;
      const nh = container.clientHeight;
      const naspect = nw / nh;
      camera.left = (-frustumSize * naspect) / 2;
      camera.right = (frustumSize * naspect) / 2;
      camera.top = frustumSize / 2;
      camera.bottom = -frustumSize / 2;
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
  }, [plane, blueprintUrl, showGrid, blueprintOpacity]);

  return (
    <div className="relative w-full h-full border border-slate-700 bg-slate-900 overflow-hidden flex flex-col">
      <div className="absolute top-2 left-3 z-10 bg-slate-800/80 backdrop-blur px-2.5 py-1 rounded text-xs font-semibold text-slate-200 border border-slate-700 select-none">
        {title}
      </div>
      <div ref={containerRef} className="w-full h-full cursor-crosshair" />
    </div>
  );
};
