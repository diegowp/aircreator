'use client';

import React from 'react';
import { useStudioStore } from '@/store/studioStore';

export const AnimationControlPanel: React.FC = () => {
  const { animationValues, setAnimationChannel } = useStudioStore();

  const aileronVal = animationValues[7] ?? 0; // CLA 7 (-1.0 to +1.0)
  const elevatorVal = animationValues[6] ?? 0; // CLA 6 (-1.0 to +1.0)
  const rudderVal = animationValues[8] ?? 0; // CLA 8 (-1.0 to +1.0)
  const gearDeployed = (animationValues[0] ?? 1) >= 0.5; // CLA 0 (0 or 1)

  return (
    <div className="absolute bottom-4 right-4 z-30 bg-slate-900/90 backdrop-blur border border-slate-700/80 rounded-lg p-3.5 shadow-2xl w-72 text-xs flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-1.5">
        <span className="font-semibold text-slate-200 flex items-center gap-1.5">
          🕹️ Cinemática de Voo (CLA)
        </span>
        <button
          onClick={() => {
            setAnimationChannel(7, 0);
            setAnimationChannel(6, 0);
            setAnimationChannel(8, 0);
          }}
          className="text-[10px] text-blue-400 hover:text-blue-300 transition"
        >
          Resetar
        </button>
      </div>

      {/* Ailerons (CLA 7) */}
      <div className="flex flex-col gap-1">
        <div className="flex justify-between text-slate-400">
          <span>Ailerons (CLA 7 - Roll)</span>
          <span className="font-mono text-slate-200">
            {aileronVal > 0 ? `+${(aileronVal * 15).toFixed(1)}°` : `${(aileronVal * 15).toFixed(1)}°`}
          </span>
        </div>
        <input
          type="range"
          min="-1"
          max="1"
          step="0.05"
          value={aileronVal}
          onChange={(e) => setAnimationChannel(7, parseFloat(e.target.value))}
          className="accent-blue-500 cursor-pointer w-full"
        />
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>Esq</span>
          <span>Neutro</span>
          <span>Dir</span>
        </div>
      </div>

      {/* Elevator (CLA 6) */}
      <div className="flex flex-col gap-1">
        <div className="flex justify-between text-slate-400">
          <span>Profundor (CLA 6 - Pitch)</span>
          <span className="font-mono text-slate-200">
            {elevatorVal > 0 ? `+${(elevatorVal * 18).toFixed(1)}°` : `${(elevatorVal * 18).toFixed(1)}°`}
          </span>
        </div>
        <input
          type="range"
          min="-1"
          max="1"
          step="0.05"
          value={elevatorVal}
          onChange={(e) => setAnimationChannel(6, parseFloat(e.target.value))}
          className="accent-blue-500 cursor-pointer w-full"
        />
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>Cabrar</span>
          <span>Neutro</span>
          <span>Picar</span>
        </div>
      </div>

      {/* Rudder (CLA 8) */}
      <div className="flex flex-col gap-1">
        <div className="flex justify-between text-slate-400">
          <span>Leme de Direção (CLA 8 - Yaw)</span>
          <span className="font-mono text-slate-200">
            {rudderVal > 0 ? `+${(rudderVal * 25).toFixed(1)}°` : `${(rudderVal * 25).toFixed(1)}°`}
          </span>
        </div>
        <input
          type="range"
          min="-1"
          max="1"
          step="0.05"
          value={rudderVal}
          onChange={(e) => setAnimationChannel(8, parseFloat(e.target.value))}
          className="accent-blue-500 cursor-pointer w-full"
        />
        <div className="flex justify-between text-[10px] text-slate-500">
          <span>Esq</span>
          <span>Neutro</span>
          <span>Dir</span>
        </div>
      </div>

      {/* Landing Gear (CLA 0) */}
      <div className="flex items-center justify-between pt-1 border-t border-slate-800">
        <span className="text-slate-400">Trem de Pouso (CLA 0)</span>
        <button
          onClick={() => setAnimationChannel(0, gearDeployed ? 0 : 1)}
          className={`px-2 py-0.5 rounded text-[11px] font-medium transition ${
            gearDeployed
              ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800/60'
              : 'bg-amber-950/80 text-amber-400 border border-amber-800/60'
          }`}
        >
          {gearDeployed ? 'Baixado (Down)' : 'Recolhido (Up)'}
        </button>
      </div>
    </div>
  );
};
