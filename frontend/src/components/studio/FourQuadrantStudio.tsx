'use client';

import React from 'react';
import { OrthographicViewport } from './OrthographicViewport';
import { PerspectiveViewport } from './PerspectiveViewport';
import { useStudioStore } from '@/store/studioStore';

export const FourQuadrantStudio: React.FC = () => {
  const {
    showWireframe,
    setShowWireframe,
    showGrid,
    setShowGrid,
    blueprintOpacity,
    setBlueprintOpacity,
    blueprints,
  } = useStudioStore();

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 select-none overflow-hidden">
      {/* Top Header / Toolbar */}
      <header className="h-12 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between px-4 z-20">
        <div className="flex items-center space-x-3">
          <span className="text-base font-bold tracking-tight text-white flex items-center gap-2">
            ✈️ AirCreator <span className="text-xs font-normal text-blue-400 bg-blue-950/60 px-2 py-0.5 rounded border border-blue-800/40">Studio 4V</span>
          </span>
          <span className="text-slate-600">|</span>
          <span className="text-xs text-slate-400">EMB-314 Super Tucano</span>
        </div>

        {/* Toolbar controls */}
        <div className="flex items-center space-x-4 text-xs">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={showWireframe}
              onChange={(e) => setShowWireframe(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-blue-600 focus:ring-0"
            />
            <span className="text-slate-300">Wireframe</span>
          </label>

          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="checkbox"
              checked={showGrid}
              onChange={(e) => setShowGrid(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-blue-600 focus:ring-0"
            />
            <span className="text-slate-300">Grade (Grid)</span>
          </label>

          <div className="flex items-center gap-2">
            <span className="text-slate-400">Opacidade Blueprint:</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={blueprintOpacity}
              onChange={(e) => setBlueprintOpacity(parseFloat(e.target.value))}
              className="w-20 accent-blue-500 cursor-pointer"
            />
          </div>
        </div>
      </header>

      {/* Main 4-Quadrant Viewport Grid (Classic CAD / Metasequoia layout) */}
      <main className="flex-1 grid grid-cols-2 grid-rows-2 gap-1 p-1 bg-slate-950">
        {/* Quadrant 1 (Top Left): Top View (Plano XZ) */}
        <OrthographicViewport
          title="Vista Superior (Top / Plano XZ)"
          plane="top"
          blueprintUrl={blueprints.topUrl}
        />

        {/* Quadrant 2 (Top Right): 3D Perspective Free View */}
        <PerspectiveViewport />

        {/* Quadrant 3 (Bottom Left): Front View (Plano XY) */}
        <OrthographicViewport
          title="Vista Frontal (Front / Plano XY)"
          plane="front"
          blueprintUrl={blueprints.frontUrl}
        />

        {/* Quadrant 4 (Bottom Right): Side View (Plano ZY) */}
        <OrthographicViewport
          title="Vista Lateral (Side / Plano ZY)"
          plane="side"
          blueprintUrl={blueprints.sideUrl}
        />
      </main>
    </div>
  );
};
