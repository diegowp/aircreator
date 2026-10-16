'use client';

import React, { useRef, useEffect } from 'react';
import * as THREE from 'three';
import { useStudioStore } from '@/store/studioStore';
import { createProceduralSuperTucanoScene, buildAircraftSceneFromApi, updateAircraftKinematics, AircraftMeshScene } from '@/lib/threeMeshBuilder';
import { Maximize2, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react';

interface OrthographicViewportProps {
  title: string;
  plane: 'top' | 'front' | 'side';
  blueprintUrl?: string;
}

export const OrthographicViewport: React.FC<OrthographicViewportProps> = ({
  title,
  plane,
  blueprintUrl,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<AircraftMeshScene | null>(null);
  const threeSceneRef = useRef<THREE.Scene | null>(null);
  const blueprintMeshRef = useRef<THREE.Mesh | null>(null);
  const cameraRef = useRef<THREE.OrthographicCamera | null>(null);
  const frustumSizeRef = useRef<number>(14);

  const {
    showWireframe,
    showGrid,
    blueprintOpacity,
    partVisibility,
    animationValues,
    wingspanM,
    lengthM,
    heightM,
    reconstructionData,
    setViewportMode,
  } = useStudioStore();

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
      if (partObj) partObj.visible = isVisible;
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

  // Update aircraft model when reconstruction data arrives or changes
  useEffect(() => {
    if (!threeSceneRef.current) return;
    const scene = threeSceneRef.current;

    if (sceneRef.current) {
      scene.remove(sceneRef.current.rootGroup);
    }

    const newScene = reconstructionData?.component_meshes
      ? buildAircraftSceneFromApi(reconstructionData)
      : createProceduralSuperTucanoScene();

    sceneRef.current = newScene;
    scene.add(newScene.rootGroup);

    // Apply visibility
    Object.entries(partVisibility).forEach(([partKey, isVisible]) => {
      const partObj = newScene.parts[partKey];
      if (partObj) partObj.visible = isVisible;
    });

    // Apply wireframe
    newScene.rootGroup.traverse((child) => {
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
  }, [reconstructionData]);

  // Update blueprint overlay with exact aspect ratio and alignment
  useEffect(() => {
    if (!threeSceneRef.current || !blueprintUrl) return;
    const scene = threeSceneRef.current;

    const loader = new THREE.TextureLoader();
    loader.load(blueprintUrl, (texture) => {
      texture.minFilter = THREE.LinearFilter;
      const imgAspect = (texture.image.width || 1) / (texture.image.height || 1);

      if (blueprintMeshRef.current) {
        scene.remove(blueprintMeshRef.current);
        blueprintMeshRef.current.geometry.dispose();
      }

      let planeW = 12;
      let planeH = 12;

      if (plane === 'top') {
        planeW = wingspanM;
        planeH = wingspanM / imgAspect;
      } else if (plane === 'side') {
        planeW = lengthM;
        planeH = lengthM / imgAspect;
      } else if (plane === 'front') {
        planeW = wingspanM;
        planeH = wingspanM / imgAspect;
      }

      const geom = new THREE.PlaneGeometry(planeW, planeH);
      const mat = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true,
        opacity: blueprintOpacity,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const planeMesh = new THREE.Mesh(geom, mat);

      if (plane === 'top') {
        // Rotate so nose points to world +Z (Up on screen) and starboard to +X (Right on screen)
        planeMesh.rotation.set(Math.PI / 2, 0, 0);
        planeMesh.position.set(0, -0.6, 0);
      } else if (plane === 'side') {
        // Rotate so top is +Y and tail is -Z (Right on screen)
        planeMesh.rotation.set(0, Math.PI / 2, 0);
        planeMesh.position.set(-0.6, 0, 0);
      } else if (plane === 'front') {
        planeMesh.rotation.set(0, 0, 0);
        planeMesh.position.set(0, 0, -0.6);
      }

      blueprintMeshRef.current = planeMesh;
      scene.add(planeMesh);
    });
  }, [blueprintUrl, blueprintOpacity, plane, wingspanM, lengthM, heightM]);

  useEffect(() => {
    if (!containerRef.current) return;
    const container = containerRef.current;
    const width = container.clientWidth || 400;
    const height = container.clientHeight || 300;

    const scene = new THREE.Scene();
    threeSceneRef.current = scene;
    scene.background = new THREE.Color(0x131722); // CAD dark background

    const aspect = width / height;
    const frustumSize = frustumSizeRef.current;
    const camera = new THREE.OrthographicCamera(
      (-frustumSize * aspect) / 2,
      (frustumSize * aspect) / 2,
      frustumSize / 2,
      -frustumSize / 2,
      0.1,
      1000
    );
    cameraRef.current = camera;

    // Camera position according to plane
    if (plane === 'top') {
      camera.position.set(0, 50, 0);
      camera.up.set(0, 0, 1); // +Z is nose forward (top of screen!)
      camera.lookAt(0, 0, 0);
    } else if (plane === 'front') {
      camera.position.set(0, 0, 50);
      camera.up.set(0, 1, 0);
      camera.lookAt(0, 0, 0);
    } else if (plane === 'side') {
      camera.position.set(50, 0, 0);
      camera.up.set(0, 1, 0);
      camera.lookAt(0, 0, 0);
    }

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Directional Lighting for clear surface shading
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0xffffff, 1.0);
    dirLight.position.set(10, 20, 20);
    scene.add(dirLight);

    // CAD Reference Grid
    if (showGrid) {
      const grid = new THREE.GridHelper(24, 24, 0x3b82f6, 0x334155);
      if (plane === 'front') grid.rotation.x = Math.PI / 2;
      if (plane === 'side') grid.rotation.z = Math.PI / 2;
      scene.add(grid);

      const axes = new THREE.AxesHelper(3.5);
      scene.add(axes);
    }

    // Initial Aircraft Model (dynamic from API or fallback)
    const aircraftScene = reconstructionData?.component_meshes
      ? buildAircraftSceneFromApi(reconstructionData)
      : createProceduralSuperTucanoScene();
    sceneRef.current = aircraftScene;
    scene.add(aircraftScene.rootGroup);

    // Apply visibility
    Object.entries(partVisibility).forEach(([partKey, isVisible]) => {
      const partObj = aircraftScene.parts[partKey];
      if (partObj) partObj.visible = isVisible;
    });

    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      if (sceneRef.current) {
        updateAircraftKinematics(sceneRef.current, animValuesRef.current);
      }
      renderer.render(scene, camera);
    };
    animate();

    // Mouse Drag Pan & Scroll Zoom for 2D Viewport
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;

    const handleMouseDown = (e: MouseEvent) => {
      isDragging = true;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;
    };

    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !cameraRef.current) return;
      const dx = (e.clientX - prevMouseX) * 0.02;
      const dy = (e.clientY - prevMouseY) * 0.02;
      prevMouseX = e.clientX;
      prevMouseY = e.clientY;

      if (plane === 'top') {
        cameraRef.current.position.x -= dx;
        cameraRef.current.position.z += dy;
      } else if (plane === 'front') {
        cameraRef.current.position.x -= dx;
        cameraRef.current.position.y += dy;
      } else if (plane === 'side') {
        cameraRef.current.position.z += dx;
        cameraRef.current.position.y += dy;
      }
    };

    const handleMouseUp = () => {
      isDragging = false;
    };

    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      if (!cameraRef.current || !container) return;
      const zoomFactor = e.deltaY < 0 ? 0.9 : 1.1;
      frustumSizeRef.current = Math.max(2, Math.min(60, frustumSizeRef.current * zoomFactor));

      const nw = container.clientWidth;
      const nh = container.clientHeight;
      const naspect = nw / nh;
      const curSize = frustumSizeRef.current;

      cameraRef.current.left = (-curSize * naspect) / 2;
      cameraRef.current.right = (curSize * naspect) / 2;
      cameraRef.current.top = curSize / 2;
      cameraRef.current.bottom = -curSize / 2;
      cameraRef.current.updateProjectionMatrix();
    };

    const dom = renderer.domElement;
    dom.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    dom.addEventListener('wheel', handleWheel, { passive: false });

    const handleResize = () => {
      if (!container) return;
      const nw = container.clientWidth;
      const nh = container.clientHeight;
      const naspect = nw / nh;
      const curSize = frustumSizeRef.current;
      camera.left = (-curSize * naspect) / 2;
      camera.right = (curSize * naspect) / 2;
      camera.top = curSize / 2;
      camera.bottom = -curSize / 2;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, nh);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      dom.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      dom.removeEventListener('wheel', handleWheel);
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animId);
      renderer.dispose();
      if (container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [plane, blueprintUrl, showGrid, blueprintOpacity]);

  const resetView = () => {
    if (!cameraRef.current || !containerRef.current) return;
    frustumSizeRef.current = 14;
    const nw = containerRef.current.clientWidth;
    const nh = containerRef.current.clientHeight;
    const naspect = nw / nh;
    const curSize = frustumSizeRef.current;

    const camera = cameraRef.current;
    camera.left = (-curSize * naspect) / 2;
    camera.right = (curSize * naspect) / 2;
    camera.top = curSize / 2;
    camera.bottom = -curSize / 2;

    if (plane === 'top') {
      camera.position.set(0, 50, 0);
      camera.lookAt(0, 0, 0);
    } else if (plane === 'front') {
      camera.position.set(0, 0, 50);
      camera.lookAt(0, 0, 0);
    } else if (plane === 'side') {
      camera.position.set(50, 0, 0);
      camera.lookAt(0, 0, 0);
    }
    camera.updateProjectionMatrix();
  };

  const maximizeMode =
    plane === 'top' ? 'top_only' : plane === 'front' ? 'front_only' : 'side_only';

  return (
    <div className="relative w-full h-full border border-slate-800 bg-slate-950 overflow-hidden flex flex-col select-none group">
      {/* Viewport Title Badge */}
      <div className="absolute top-2 left-3 z-10 bg-slate-900/80 backdrop-blur px-2.5 py-1 rounded text-xs font-semibold text-slate-200 border border-slate-700/80 shadow">
        {title}
      </div>

      {/* Control Buttons */}
      <div className="absolute top-2 right-3 z-10 opacity-70 group-hover:opacity-100 transition flex items-center gap-1 bg-slate-900/80 backdrop-blur p-1 rounded-lg border border-slate-800 text-[10px]">
        <button
          onClick={resetView}
          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
          title="Centralizar e Resetar Zoom"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>
        <button
          onClick={() => setViewportMode(maximizeMode as any)}
          className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white transition"
          title="Maximizar esta vista"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* WebGL Canvas */}
      <div ref={containerRef} className="w-full h-full cursor-crosshair" />

      {/* Navigation Hint HUD */}
      <div className="absolute bottom-2 left-3 z-10 pointer-events-none text-[10px] text-slate-500 bg-slate-950/60 backdrop-blur px-2 py-0.5 rounded border border-slate-800/40">
        Clique e arraste: Pan 2D | Scroll: Zoom
      </div>
    </div>
  );
};
