'use client';

import React from 'react';
import { TopNavbar } from './TopNavbar';
import { HierarchySidebar } from './HierarchySidebar';
import { OrthographicViewport } from './OrthographicViewport';
import { PerspectiveViewport } from './PerspectiveViewport';
import { AnimationControlPanel } from './AnimationControlPanel';
import { BlueprintUploadModal } from './BlueprintUploadModal';
import { ValidationReportModal } from './ValidationReportModal';
import { useStudioStore } from '@/store/studioStore';
import { ShieldCheck, HardDrive, Compass } from 'lucide-react';

export const FourQuadrantStudio: React.FC = () => {
  const {
    viewportMode,
    blueprints,
    aircraftName,
    wingspanM,
    lengthM,
    setModals,
    triggerReconstruction,
    reconstructionData,
  } = useStudioStore();

  React.useEffect(() => {
    if (!reconstructionData) {
      triggerReconstruction();
    }
  }, []);

  return (
    <div className="flex flex-col h-screen w-screen bg-slate-950 text-slate-100 select-none overflow-hidden font-sans">
      {/* Top Application Navbar */}
      <TopNavbar />

      {/* Main Studio Workspace (Viewports + Hierarchy Sidebar) */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Viewport Area */}
        <div className="flex-1 flex flex-col relative overflow-hidden bg-slate-950">
          {viewportMode === 'four_quadrants' && (
            <main className="flex-1 grid grid-cols-2 grid-rows-2 gap-1 p-1 bg-slate-950">
              {/* Quadrant 1 (Top Left): Top View (Plano XZ) */}
              <OrthographicViewport
                title="Vista Superior (Top / Plano XZ)"
                plane="top"
                blueprintUrl={blueprints.topUrl}
              />

              {/* Quadrant 2 (Top Right): 3D Perspective Free Orbit */}
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
          )}

          {viewportMode === 'single_3d' && (
            <main className="flex-1 p-1 bg-slate-950">
              <PerspectiveViewport />
            </main>
          )}

          {viewportMode === 'top_only' && (
            <main className="flex-1 p-1 bg-slate-950">
              <OrthographicViewport
                title="Vista Superior (Top / Plano XZ)"
                plane="top"
                blueprintUrl={blueprints.topUrl}
              />
            </main>
          )}

          {viewportMode === 'front_only' && (
            <main className="flex-1 p-1 bg-slate-950">
              <OrthographicViewport
                title="Vista Frontal (Front / Plano XY)"
                plane="front"
                blueprintUrl={blueprints.frontUrl}
              />
            </main>
          )}

          {viewportMode === 'side_only' && (
            <main className="flex-1 p-1 bg-slate-950">
              <OrthographicViewport
                title="Vista Lateral (Side / Plano ZY)"
                plane="side"
                blueprintUrl={blueprints.sideUrl}
              />
            </main>
          )}

          {/* Realtime Interactive Flight Kinematics Slider Floating Widget */}
          <AnimationControlPanel />
        </div>

        {/* Metasequoia-style Scene Hierarchy & Part Visibility Sidebar */}
        <HierarchySidebar />
      </div>

      {/* Bottom Status Bar */}
      <footer className="h-7 bg-slate-900 border-t border-slate-800 px-4 flex items-center justify-between text-[11px] text-slate-400 z-20 select-none">
        <div className="flex items-center space-x-4">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-slate-300 font-medium">Motor Paramétrico Ativo</span>
          </div>
          <span className="text-slate-700">|</span>
          <div className="flex items-center gap-1.5">
            <Compass className="w-3.5 h-3.5 text-blue-400" />
            <span>YSFlight LH: +X Dir, +Y Cima, +Z Nariz</span>
          </div>
          <span className="text-slate-700">|</span>
          <span className="text-slate-400 font-mono">
            {aircraftName} ({wingspanM}m × {lengthM}m)
          </span>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => setModals({ validation: true })}
            className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 transition"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>12/12 Regras de Engenharia Aprovadas</span>
          </button>
          <span className="text-slate-700">|</span>
          <div className="flex items-center gap-1 text-slate-400">
            <HardDrive className="w-3.5 h-3.5 text-slate-500" />
            <span>YSFlight SRF + DNM 16-bit</span>
          </div>
        </div>
      </footer>

      {/* Modals */}
      <BlueprintUploadModal />
      <ValidationReportModal />
    </div>
  );
};
