'use client';

import React from 'react';
import {
  Plane,
  UploadCloud,
  RefreshCw,
  ShieldCheck,
  Download,
  FileCode,
  LayoutGrid,
  Maximize2,
  Sliders,
  CheckCircle,
} from 'lucide-react';
import { useStudioStore, ViewportMode } from '@/store/studioStore';

export const TopNavbar: React.FC = () => {
  const {
    aircraftName,
    viewportMode,
    setViewportMode,
    showWireframe,
    setShowWireframe,
    showGrid,
    setShowGrid,
    blueprintOpacity,
    setBlueprintOpacity,
    isProcessing,
    statusMessage,
    setModals,
    triggerReconstruction,
    triggerValidation,
    downloadYsflightZip,
    downloadObjFiles,
  } = useStudioStore();

  return (
    <header className="h-14 border-b border-slate-800 bg-slate-900/95 backdrop-blur flex items-center justify-between px-4 z-20 select-none shadow-md">
      {/* Brand & Aircraft Title */}
      <div className="flex items-center space-x-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-blue-600/20 border border-blue-500/40 text-blue-400">
            <Plane className="w-4 h-4" />
          </div>
          <span className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
            AirCreator <span className="text-[10px] font-mono font-medium text-blue-400 bg-blue-950/80 px-2 py-0.5 rounded border border-blue-800/60">STUDIO 4V</span>
          </span>
        </div>

        <span className="text-slate-700">|</span>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-slate-200">{aircraftName}</span>
          <span className="text-[10px] text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 px-2 py-0.5 rounded-full flex items-center gap-1">
            <CheckCircle className="w-3 h-3" /> YSFlight Rigged
          </span>
        </div>
      </div>

      {/* Viewport Mode Switcher */}
      <div className="flex items-center bg-slate-950/70 p-1 rounded-lg border border-slate-800 text-xs">
        <button
          onClick={() => setViewportMode('four_quadrants')}
          className={`px-2.5 py-1 rounded-md transition flex items-center gap-1.5 ${
            viewportMode === 'four_quadrants'
              ? 'bg-blue-600 text-white font-medium shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
          title="Modo Metasequoia: 4 Quadrantes (Top, Side, Front, 3D)"
        >
          <LayoutGrid className="w-3.5 h-3.5" />
          <span>4 Vistas</span>
        </button>

        <button
          onClick={() => setViewportMode('single_3d')}
          className={`px-2.5 py-1 rounded-md transition flex items-center gap-1.5 ${
            viewportMode === 'single_3d'
              ? 'bg-blue-600 text-white font-medium shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
          title="Viewport 3D Livre Expandido"
        >
          <Maximize2 className="w-3.5 h-3.5" />
          <span>3D Livre</span>
        </button>

        <button
          onClick={() => setViewportMode('top_only')}
          className={`px-2 py-1 rounded-md transition text-[11px] ${
            viewportMode === 'top_only'
              ? 'bg-blue-600 text-white font-medium shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Top
        </button>
        <button
          onClick={() => setViewportMode('front_only')}
          className={`px-2 py-1 rounded-md transition text-[11px] ${
            viewportMode === 'front_only'
              ? 'bg-blue-600 text-white font-medium shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Front
        </button>
        <button
          onClick={() => setViewportMode('side_only')}
          className={`px-2 py-1 rounded-md transition text-[11px] ${
            viewportMode === 'side_only'
              ? 'bg-blue-600 text-white font-medium shadow'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Side
        </button>
      </div>

      {/* Center Status Notification */}
      <div className="hidden lg:flex items-center gap-2 px-3 py-1 bg-slate-950/60 rounded-full border border-slate-800 text-[11px]">
        {isProcessing ? (
          <span className="flex items-center gap-1.5 text-blue-400">
            <RefreshCw className="w-3 h-3 animate-spin" />
            <span>{statusMessage}</span>
          </span>
        ) : (
          <span className="text-slate-400 truncate max-w-xs">{statusMessage}</span>
        )}
      </div>

      {/* Display & Action Buttons */}
      <div className="flex items-center space-x-3 text-xs">
        {/* Render Toggles */}
        <div className="flex items-center gap-3 pr-3 border-r border-slate-800">
          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-white">
            <input
              type="checkbox"
              checked={showWireframe}
              onChange={(e) => setShowWireframe(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-blue-600 focus:ring-0"
            />
            <span className="text-[11px]">Wireframe</span>
          </label>

          <label className="flex items-center gap-1.5 cursor-pointer text-slate-300 hover:text-white">
            <input
              type="checkbox"
              checked={showGrid}
              onChange={(e) => setShowGrid(e.target.checked)}
              className="rounded bg-slate-800 border-slate-700 text-blue-600 focus:ring-0"
            />
            <span className="text-[11px]">Grid</span>
          </label>

          <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
            <span>Opac:</span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={blueprintOpacity}
              onChange={(e) => setBlueprintOpacity(parseFloat(e.target.value))}
              className="w-16 accent-blue-500 cursor-pointer"
              title="Opacidade das Blueprints"
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setModals({ upload: true })}
            className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition text-[11px]"
            title="Importar nova blueprint e calibrar"
          >
            <UploadCloud className="w-3.5 h-3.5 text-blue-400" />
            <span>Blueprint</span>
          </button>

          <button
            onClick={triggerReconstruction}
            disabled={isProcessing}
            className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition text-[11px] disabled:opacity-50"
            title="Recalcular lofting e espelhamento"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-amber-400 ${isProcessing ? 'animate-spin' : ''}`} />
            <span>Reconstruir</span>
          </button>

          <button
            onClick={triggerValidation}
            disabled={isProcessing}
            className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition text-[11px]"
            title="Executar checklist de 12 itens aeronáuticos"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Validar</span>
          </button>

          <button
            onClick={downloadYsflightZip}
            disabled={isProcessing}
            className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium shadow-md flex items-center gap-1.5 transition text-[11px] disabled:opacity-50"
            title="Baixar pacote ZIP completo com DNM, SRF, DAT, LST"
          >
            <Download className="w-3.5 h-3.5" />
            <span>ZIP YSFlight</span>
          </button>

          <button
            onClick={downloadObjFiles}
            disabled={isProcessing}
            className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition text-[11px]"
            title="Exportar geometria em formato OBJ / MTL padrão"
          >
            <FileCode className="w-3.5 h-3.5 text-slate-300" />
            <span>OBJ</span>
          </button>
        </div>
      </div>
    </header>
  );
};
