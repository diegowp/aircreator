'use client';

import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { useStudioStore } from '@/store/studioStore';
import { createProceduralSuperTucanoScene, updateAircraftKinematics, AircraftMeshScene } from '@/lib/threeMeshBuilder';
import { Eye, RotateCcw, Video } from 'lucide-react';

export const PerspectiveViewport: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<AircraftMeshScene | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);

  const { showWireframe, showGrid, partVisibility, animationValues } = useStudioStore();

  // Animation values ref so the animate loop accesses the latest values without re-mounting
  const animValuesRef = useRef(animationValues);
  useEffect(() => {
    animValuesRef.current = animationValues;
  }, [animationValues]);

  // Update part visibility reactively
  useEffect(() => {
    if (!sceneRef.current) return;
    const parts = sceneRef.current.parts;
    Object.entries(partVisibility).forEach(([partKey, isVisible]) => {
      const partObj = parts[partKey];
      if (partObj) {
        partObj.visible = isVisible;
      }
    });
  }, [partVisibility]);

  // Update wireframe reactively
  useEffect(() => {
    if (!sceneRef.current) return;
    sceneRef.current.rootGroup.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        if (Array.isArray(child.material)) {
          child.material.forEach((m) => {
            if ('wireframe' in m) m.wireframe = showWireframe;
          });
        } else if ('wireframe' in child.material) {
          child.material.wireframe = showWireframe;
        }
      }
    });
  }, [showWireframe]);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const width = container.clientWidth || 400;
    const height = container.clientHeight || 300;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0c0f17); // Professional dark cockpit slate

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(11, 7, 12);
    camera.lookAt(0, 0.5, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    // Orbit Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxDistance = 60;
    controls.minDistance = 2;
    controls.target.set(0, 0.5, 0);
    controlsRef.current = controls;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
    scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xffffff, 1.8);
    sunLight.position.set(15, 25, 15);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    scene.add(sunLight);

    const fillLight = new THREE.DirectionalLight(0x38bdf8, 0.6); // Cyan sky bounce
    fillLight.position.set(-15, 10, -10);
    scene.add(fillLight);

    // Ground Grid & Axes
    let gridHelper: THREE.GridHelper | null = null;
    let axesHelper: THREE.AxesHelper | null = null;
    if (showGrid) {
      gridHelper = new THREE.GridHelper(30, 30, 0x3b82f6, 0x1e293b);
      gridHelper.position.y = -1.2; // Wheel ground contact level
      scene.add(gridHelper);

      axesHelper = new THREE.AxesHelper(3);
      axesHelper.position.set(0, -1.19, 0);
      scene.add(axesHelper);
    }

    // Aeronautical Procedural Aircraft Model
    const aircraftScene = createProceduralSuperTucanoScene();
    sceneRef.current = aircraftScene;
    scene.add(aircraftScene.rootGroup);

    // Initial visibility apply
    Object.entries(partVisibility).forEach(([partKey, isVisible]) => {
      const partObj = aircraftScene.parts[partKey];
      if (partObj) partObj.visible = isVisible;
    });

    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);

      // Realtime Flight Kinematics
      updateAircraftKinematics(aircraftScene, animValuesRef.current);

      controls.update();
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
      controls.dispose();
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [showGrid]);

  const setCameraView = (type: 'iso' | 'front' | 'top' | 'side' | 'chase') => {
    if (!cameraRef.current || !controlsRef.current) return;
    const camera = cameraRef.current;
    const controls = controlsRef.current;

    switch (type) {
      case 'iso':
        camera.position.set(11, 7, 12);
        controls.target.set(0, 0.5, 0);
        break;
      case 'front':
        camera.position.set(0, 0.5, 14);
        controls.target.set(0, 0.5, 0);
        break;
      case 'top':
        camera.position.set(0, 16, 0.1);
        controls.target.set(0, 0, 0);
        break;
      case 'side':
        camera.position.set(14, 0.5, 0);
        controls.target.set(0, 0.5, 0);
        break;
      case 'chase':
        camera.position.set(0, 2.5, -12);
        controls.target.set(0, 0.5, 2);
        break;
    }
    controls.update();
  };

  return (
    <div className="relative w-full h-full border border-slate-800 bg-slate-950 overflow-hidden flex flex-col select-none group">
      {/* Top HUD Badge */}
      <div className="absolute top-2 left-3 z-10 flex items-center gap-2">
        <div className="bg-slate-900/80 backdrop-blur px-2.5 py-1 rounded text-xs font-semibold text-blue-400 border border-slate-700/80 flex items-center gap-1.5 shadow">
          <Video className="w-3 h-3" />
          <span>3D Perspective (Livre / Orbit)</span>
        </div>
      </div>

      {/* Camera View Presets HUD */}
      <div className="absolute top-2 right-3 z-10 opacity-70 group-hover:opacity-100 transition flex items-center gap-1 bg-slate-900/80 backdrop-blur p-1 rounded-lg border border-slate-800 text-[10px]">
        <button
          onClick={() => setCameraView('iso')}
          className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition"
          title="Vista Isométrica 3D"
        >
          Iso
        </button>
        <button
          onClick={() => setCameraView('front')}
          className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition"
          title="Vista Frontal (Nariz)"
        >
          Front
        </button>
        <button
          onClick={() => setCameraView('top')}
          className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition"
          title="Vista Superior (Dorso)"
        >
          Top
        </button>
        <button
          onClick={() => setCameraView('side')}
          className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition"
          title="Vista Lateral (Bombordo)"
        >
          Side
        </button>
        <button
          onClick={() => setCameraView('chase')}
          className="px-2 py-0.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white transition"
          title="Vista de Perseguição Traseira"
        >
          Chase
        </button>
        <button
          onClick={() => setCameraView('iso')}
          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
          title="Resetar Câmera"
        >
          <RotateCcw className="w-3 h-3" />
        </button>
      </div>

      {/* WebGL Canvas */}
      <div ref={containerRef} className="w-full h-full cursor-grab active:cursor-grabbing" />

      {/* Orbit Navigation Hint HUD */}
      <div className="absolute bottom-2 left-3 z-10 pointer-events-none text-[10px] text-slate-500 bg-slate-950/60 backdrop-blur px-2 py-0.5 rounded border border-slate-800/40">
        Botão esquerdo: Orbitar | Botão direito: Pan | Scroll: Zoom
      </div>
    </div>
  );
};
