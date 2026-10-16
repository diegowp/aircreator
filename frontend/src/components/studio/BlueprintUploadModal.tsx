'use client';

import React, { useState } from 'react';
import { X, UploadCloud, Check, AlertCircle, Plane, Sparkles } from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';
import { airCreatorApi } from '@/lib/api';

const PRESETS = [
  {
    name: 'EMB-314 Super Tucano',
    preset: 'SUPER_TUCANO',
    wingspan: 11.14,
    length: 11.38,
    height: 3.97,
    category: 'Ataque Leve / Treinamento Avançado',
  },
  {
    name: 'Neiva T-25 Universal',
    preset: 'TRAINER',
    wingspan: 9.5,
    length: 8.6,
    height: 3.0,
    category: 'Treinamento Primário FAB',
  },
  {
    name: 'EMB-312 Tucano',
    preset: 'TRAINER',
    wingspan: 11.14,
    length: 9.86,
    height: 3.4,
    category: 'Treinamento Básico',
  },
];

export const BlueprintUploadModal: React.FC = () => {
  const {
    isUploadModalOpen,
    setModals,
    aircraftName,
    wingspanM,
    lengthM,
    heightM,
    setAircraftDimensions,
    setActiveBlueprintPath,
    setBlueprints,
    triggerReconstruction,
  } = useStudioStore();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [localName, setLocalName] = useState(aircraftName);
  const [localWingspan, setLocalWingspan] = useState(wingspanM);
  const [localLength, setLocalLength] = useState(lengthM);
  const [localHeight, setLocalHeight] = useState(heightM);
  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isUploadModalOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      setPreviewUrl(URL.createObjectURL(file));
      setErrorMsg(null);
    }
  };

  const applyPreset = (preset: typeof PRESETS[0]) => {
    setLocalName(preset.name);
    setLocalWingspan(preset.wingspan);
    setLocalLength(preset.length);
    setLocalHeight(preset.height);
  };

  const handleConfirm = async () => {
    setIsProcessing(true);
    setErrorMsg(null);
    try {
      setAircraftDimensions({
        name: localName,
        wingspan: localWingspan,
        length: localLength,
        height: localHeight,
      });

      if (selectedFile) {
        const decomp = await airCreatorApi.decomposeBlueprint(selectedFile);
        if (decomp.saved_path) {
          setActiveBlueprintPath(decomp.saved_path);
        }
        if (decomp.top_view?.image_base64) {
          setBlueprints({
            topUrl: `data:image/png;base64,${decomp.top_view.image_base64}`,
            frontUrl: decomp.front_view?.image_base64
              ? `data:image/png;base64,${decomp.front_view.image_base64}`
              : undefined,
            sideUrl: decomp.side_view?.image_base64
              ? `data:image/png;base64,${decomp.side_view.image_base64}`
              : undefined,
          });
        }
      }

      await triggerReconstruction();
      setModals({ upload: false });
    } catch (err: any) {
      setErrorMsg(err.message || 'Falha ao processar blueprint');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 select-none">
      <div className="w-full max-w-2xl bg-slate-900 border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden text-slate-100">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/50">
          <div className="flex items-center gap-2.5">
            <Plane className="w-5 h-5 text-blue-400" />
            <h2 className="text-base font-semibold">Carregar Nova Blueprint de Aeronave</h2>
          </div>
          <button
            onClick={() => setModals({ upload: false })}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto max-h-[75vh] space-y-5">
          {/* Presets Bar */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Presets Pré-configurados:
            </label>
            <div className="grid grid-cols-3 gap-2">
              {PRESETS.map((p) => (
                <button
                  key={p.name}
                  type="button"
                  onClick={() => applyPreset(p)}
                  className={`p-2.5 rounded-lg border text-left transition flex flex-col justify-between ${
                    localName === p.name
                      ? 'bg-blue-950/50 border-blue-500 text-white shadow-md'
                      : 'bg-slate-800/40 border-slate-700/60 hover:bg-slate-800 text-slate-300'
                  }`}
                >
                  <span className="text-xs font-semibold truncate">{p.name}</span>
                  <span className="text-[10px] text-slate-400 mt-1">
                    {p.wingspan}m × {p.length}m
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Blueprint Drag & Drop Area */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2">
              Arquivo da Blueprint (3 Vistas: Top, Front, Side):
            </label>
            <div className="border-2 border-dashed border-slate-700 hover:border-blue-500/80 rounded-xl p-4 bg-slate-950/40 flex flex-col items-center justify-center transition cursor-pointer relative">
              <input
                type="file"
                accept="image/*"
                onChange={handleFileChange}
                className="absolute inset-0 opacity-0 cursor-pointer w-full h-full"
              />
              {previewUrl ? (
                <div className="flex flex-col items-center gap-2">
                  <img
                    src={previewUrl}
                    alt="Blueprint Preview"
                    className="max-h-40 rounded border border-slate-700 object-contain"
                  />
                  <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                    <Check className="w-3.5 h-3.5" /> {selectedFile?.name || 'Blueprint Selecionada'}
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2 py-3 text-center">
                  <UploadCloud className="w-8 h-8 text-blue-400" />
                  <span className="text-xs font-medium text-slate-300">
                    Arraste a imagem ou clique para selecionar
                  </span>
                  <span className="text-[10px] text-slate-500">
                    Formatos suportados: JPG, PNG, WEBP (decomposição automatizada por OpenCV)
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Aeronautical Specs Form */}
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                Nome da Aeronave
              </label>
              <input
                type="text"
                value={localName}
                onChange={(e) => setLocalName(e.target.value)}
                className="w-full px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-white focus:outline-none focus:border-blue-500 font-medium"
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                Envergadura (Wingspan em metros)
              </label>
              <input
                type="number"
                step="0.01"
                value={localWingspan}
                onChange={(e) => setLocalWingspan(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                Comprimento Total (Length em metros)
              </label>
              <input
                type="number"
                step="0.01"
                value={localLength}
                onChange={(e) => setLocalLength(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            <div>
              <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                Altura Total (Height em metros)
              </label>
              <input
                type="number"
                step="0.01"
                value={localHeight}
                onChange={(e) => setLocalHeight(parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-white focus:outline-none focus:border-blue-500 font-mono"
              />
            </div>

            <div className="flex flex-col justify-end">
              <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/60 text-[10px] text-slate-400">
                Calibração YSFlight: Eixo X=0 centralizado, Y=0 Linha de empuxo, Z=0 Bordo de ataque.
              </div>
            </div>
          </div>

          {errorMsg && (
            <div className="p-3 rounded-lg bg-red-950/50 border border-red-800/60 text-red-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-3.5 border-t border-slate-800 bg-slate-950/60 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={() => setModals({ upload: false })}
            className="px-4 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:bg-slate-800 transition"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isProcessing}
            className="px-5 py-1.5 rounded-lg text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-lg transition flex items-center gap-2 disabled:opacity-50"
          >
            {isProcessing ? 'Processando OpenCV...' : 'Decompor & Gerar Modelo 3D'}
          </button>
        </div>
      </div>
    </div>
  );
};
