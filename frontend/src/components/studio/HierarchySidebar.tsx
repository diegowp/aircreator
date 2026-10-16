'use client';

import React from 'react';
import { Eye, EyeOff, Layers, Box, Cpu } from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';

interface PartItem {
  id: string;
  name: string;
  category: string;
  claBadge?: string;
  vertices: number;
  faces: number;
}

const AIRCRAFT_PARTS: PartItem[] = [
  { id: 'fuselagem', name: 'Fuselagem Principal & Nariz', category: 'Estrutura Central', claBadge: 'PCK_0', vertices: 288, faces: 256 },
  { id: 'wing_r', name: 'Asa Direita (Starboard)', category: 'Superfície Alar', claBadge: 'PCK_1', vertices: 96, faces: 80 },
  { id: 'aileron_d', name: 'Aileron Direito Móvel', category: 'Controle de Voo', claBadge: 'CLA 7 (Roll)', vertices: 48, faces: 40 },
  { id: 'wing_l', name: 'Asa Esquerda (Port)', category: 'Superfície Alar', claBadge: 'PCK_2', vertices: 96, faces: 80 },
  { id: 'aileron_lef', name: 'Aileron Esquerdo Móvel', category: 'Controle de Voo', claBadge: 'CLA 7 (Roll)', vertices: 48, faces: 40 },
  { id: 'elevator_1', name: 'Estabilizador Horizontal', category: 'Empenagem', claBadge: 'PCK_3', vertices: 64, faces: 52 },
  { id: 'elevator', name: 'Profundor Móvel', category: 'Controle de Voo', claBadge: 'CLA 6 (Pitch)', vertices: 48, faces: 40 },
  { id: 'rudder_1', name: 'Estabilizador Vertical (Fin)', category: 'Empenagem', claBadge: 'PCK_4', vertices: 56, faces: 46 },
  { id: 'rudder_2', name: 'Leme de Direção Móvel', category: 'Controle de Voo', claBadge: 'CLA 8 (Yaw)', vertices: 48, faces: 40 },
  { id: 'helice', name: 'Hélice Hartzell 5 Pás', category: 'Propulsão', claBadge: 'CLA 18 (Spin)', vertices: 120, faces: 90 },
];

export const HierarchySidebar: React.FC = () => {
  const {
    partVisibility,
    setPartVisibility,
    selectedPartName,
    selectPart,
    aircraftName,
  } = useStudioStore();

  const totalVertices = AIRCRAFT_PARTS.reduce((sum, p) => sum + p.vertices, 0);
  const totalFaces = AIRCRAFT_PARTS.reduce((sum, p) => sum + p.faces, 0);

  const toggleAll = (visible: boolean) => {
    AIRCRAFT_PARTS.forEach((p) => setPartVisibility(p.id, visible));
  };

  return (
    <aside className="w-80 h-full bg-slate-900 border-l border-slate-800 flex flex-col text-xs z-10 shadow-xl select-none">
      {/* Header */}
      <div className="p-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-blue-400" />
          <span className="font-semibold text-slate-200">Hierarquia de Peças</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => toggleAll(true)}
            title="Exibir todas as peças"
            className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-[10px] text-slate-300 transition"
          >
            Todas
          </button>
          <button
            onClick={() => toggleAll(false)}
            title="Ocultar todas as peças"
            className="px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-[10px] text-slate-400 transition"
          >
            Nenhuma
          </button>
        </div>
      </div>

      {/* Model summary bar */}
      <div className="px-3.5 py-2 bg-slate-950/30 border-b border-slate-800/80 flex justify-between text-[11px] text-slate-400">
        <span className="truncate font-medium text-slate-300">{aircraftName}</span>
        <span className="font-mono text-blue-400">
          {totalVertices}v / {totalFaces}f
        </span>
      </div>

      {/* Parts List (Metasequoia style) */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {AIRCRAFT_PARTS.map((part) => {
          const isVisible = partVisibility[part.id] ?? true;
          const isSelected = selectedPartName === part.id;

          return (
            <div
              key={part.id}
              onClick={() => selectPart(isSelected ? null : part.id)}
              className={`group flex items-center justify-between p-2 rounded-md transition cursor-pointer border ${
                isSelected
                  ? 'bg-blue-950/50 border-blue-500/60 text-white'
                  : 'bg-slate-850 hover:bg-slate-800/70 border-slate-800/60 text-slate-300'
              }`}
            >
              <div className="flex items-center gap-2.5 min-w-0">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setPartVisibility(part.id, !isVisible);
                  }}
                  className={`p-1 rounded transition ${
                    isVisible
                      ? 'text-emerald-400 hover:text-emerald-300 hover:bg-emerald-950/40'
                      : 'text-slate-600 hover:text-slate-400 hover:bg-slate-800'
                  }`}
                  title={isVisible ? 'Ocultar peça no 3D' : 'Exibir peça no 3D'}
                >
                  {isVisible ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
                </button>

                <div className="flex flex-col min-w-0">
                  <span className={`text-[11px] font-medium truncate ${isVisible ? 'text-slate-200' : 'text-slate-500 line-through'}`}>
                    {part.name}
                  </span>
                  <span className="text-[10px] text-slate-500 truncate">{part.category}</span>
                </div>
              </div>

              <div className="flex items-center gap-1.5 flex-shrink-0">
                {part.claBadge && (
                  <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-blue-900/40 text-blue-300 border border-blue-800/40">
                    {part.claBadge}
                  </span>
                )}
                <span className="text-[10px] font-mono text-slate-500">
                  {part.vertices}v
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer Info */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/80 text-[10px] text-slate-400 flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1">
            <Box className="w-3 h-3 text-slate-500" /> Formato YSFlight:
          </span>
          <span className="font-mono text-slate-200">SRF v20000401 + DNM</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1">
            <Cpu className="w-3 h-3 text-slate-500" /> Rigging Cinemático:
          </span>
          <span className="text-emerald-400 font-medium">Hinges CNT Ativos</span>
        </div>
      </div>
    </aside>
  );
};
