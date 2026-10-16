'use client';

import React, { useState } from 'react';
import {
  X,
  UploadCloud,
  Check,
  AlertCircle,
  Plane,
  Sparkles,
  Layers,
  Key,
  Info,
} from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';

const PRESETS = [
  {
    name: 'EMB-314 Super Tucano',
    preset: 'SUPER_TUCANO',
    wingspan: 11.14,
    length: 11.38,
    height: 3.97,
    category: 'Ataque Leve / Turboélice',
  },
  {
    name: 'Neiva T-25 Universal',
    preset: 'TRAINER',
    wingspan: 9.5,
    length: 8.6,
    height: 3.0,
    category: 'Treinamento Primário',
  },
  {
    name: 'F-15 Eagle / Caça a Jato',
    preset: 'FIGHTER',
    wingspan: 13.05,
    length: 19.43,
    height: 5.63,
    category: 'Caça Superioridade Aérea',
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
    geminiApiKey,
    setGeminiApiKey,
    uploadAndReconstruct,
  } = useStudioStore();

  const [uploadMode, setUploadMode] = useState<'separate' | 'single'>('separate');

  // Separate views
  const [topFile, setTopFile] = useState<File | null>(null);
  const [topPreview, setTopPreview] = useState<string | null>(null);

  const [sideFile, setSideFile] = useState<File | null>(null);
  const [sidePreview, setSidePreview] = useState<string | null>(null);

  const [frontFile, setFrontFile] = useState<File | null>(null);
  const [frontPreview, setFrontPreview] = useState<string | null>(null);

  // Single blueprint sheet
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [singlePreview, setSinglePreview] = useState<string | null>(null);

  // Aircraft specs
  const [localName, setLocalName] = useState(aircraftName);
  const [localWingspan, setLocalWingspan] = useState(wingspanM);
  const [localLength, setLocalLength] = useState(lengthM);
  const [localHeight, setLocalHeight] = useState(heightM);
  const [localApiKey, setLocalApiKey] = useState(geminiApiKey);

  const [isProcessing, setIsProcessing] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isUploadModalOpen) return null;

  const handleSeparateFile = (view: 'top' | 'side' | 'front', file: File) => {
    const url = URL.createObjectURL(file);
    if (view === 'top') {
      setTopFile(file);
      setTopPreview(url);
    } else if (view === 'side') {
      setSideFile(file);
      setSidePreview(url);
    } else {
      setFrontFile(file);
      setFrontPreview(url);
    }
    setErrorMsg(null);
  };

  const handleSingleFile = (file: File) => {
    setSingleFile(file);
    setSinglePreview(URL.createObjectURL(file));
    setErrorMsg(null);
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
      const formData = new FormData();

      if (uploadMode === 'separate') {
        if (!topFile && !sideFile && !frontFile) {
          throw new Error('Por favor selecione pelo menos uma das 3 vistas (Superior, Lateral ou Frontal).');
        }
        if (topFile) formData.append('top_file', topFile);
        if (sideFile) formData.append('side_file', sideFile);
        if (frontFile) formData.append('front_file', frontFile);
      } else {
        if (!singleFile) {
          throw new Error('Por favor selecione o arquivo com a blueprint da aeronave.');
        }
        formData.append('blueprint_file', singleFile);
      }

      formData.append('aircraft_name', localName.trim() || 'Aeronave Reconstruída');
      formData.append('wingspan_m', String(localWingspan));
      formData.append('length_m', String(localLength));
      formData.append('height_m', String(localHeight));

      const apiKey = localApiKey.trim();
      if (apiKey) {
        formData.append('gemini_api_key', apiKey);
        setGeminiApiKey(apiKey);
      }

      await uploadAndReconstruct(formData);
      setModals({ upload: false });
    } catch (err: any) {
      setErrorMsg(err.message || 'Falha ao processar imagens e reconstruir aeronave.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 select-none">
      <div className="w-full max-w-3xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl flex flex-col overflow-hidden text-slate-100 animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-blue-600/20 text-blue-400 rounded-lg border border-blue-500/30">
              <Plane className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-100">
                Reconstrução 3D com Gemini Vision AI
              </h2>
              <p className="text-[11px] text-slate-400">
                Alimente qualquer aeronave ou objeto paramétrico a partir de blueprints
              </p>
            </div>
          </div>
          <button
            onClick={() => setModals({ upload: false })}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto max-h-[78vh] space-y-5">
          {/* Tabs: 3 Vistas Separadas vs Folha Única */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-blue-400" /> Método de Fornecimento das Vistas:
              </label>
              <span className="text-[10px] text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded-full font-medium">
                Recomendado: 3 Vistas Separadas
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 p-1 bg-slate-950/60 rounded-xl border border-slate-800">
              <button
                type="button"
                onClick={() => setUploadMode('separate')}
                className={`py-2 px-3 rounded-lg text-xs font-medium transition flex items-center justify-center gap-2 ${
                  uploadMode === 'separate'
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>3 Vistas Separadas (Alta Precisão)</span>
              </button>
              <button
                type="button"
                onClick={() => setUploadMode('single')}
                className={`py-2 px-3 rounded-lg text-xs font-medium transition flex items-center justify-center gap-2 ${
                  uploadMode === 'single'
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                <span>Folha Blueprint Única (Decomposição)</span>
              </button>
            </div>
          </div>

          {/* Upload Area: Mode 1 (3 Vistas Separadas) */}
          {uploadMode === 'separate' ? (
            <div>
              <div className="grid grid-cols-3 gap-3">
                {/* Vista Superior */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1">
                    Vista Superior (Top)
                  </span>
                  <div className="h-32 border-2 border-dashed border-slate-700 hover:border-blue-500/80 rounded-xl bg-slate-950/40 p-2 flex flex-col items-center justify-center relative cursor-pointer group transition overflow-hidden">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => e.target.files?.[0] && handleSeparateFile('top', e.target.files[0])}
                      className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10"
                    />
                    {topPreview ? (
                      <div className="relative w-full h-full flex items-center justify-center">
                        <img
                          src={topPreview}
                          alt="Top View"
                          className="max-h-full max-w-full object-contain rounded"
                        />
                        <div className="absolute bottom-1 right-1 bg-emerald-600/90 text-white p-1 rounded-full shadow">
                          <Check className="w-3 h-3" />
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center text-center p-2">
                        <UploadCloud className="w-6 h-6 text-slate-400 group-hover:text-blue-400 transition" />
                        <span className="text-[10px] text-slate-300 font-medium mt-1">
                          Planta (Asa/Fuselagem)
                        </span>
                        <span className="text-[9px] text-slate-500">Clique ou arraste</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Vista Lateral */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1">
                    Vista Lateral (Side)
                  </span>
                  <div className="h-32 border-2 border-dashed border-slate-700 hover:border-blue-500/80 rounded-xl bg-slate-950/40 p-2 flex flex-col items-center justify-center relative cursor-pointer group transition overflow-hidden">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => e.target.files?.[0] && handleSeparateFile('side', e.target.files[0])}
                      className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10"
                    />
                    {sidePreview ? (
                      <div className="relative w-full h-full flex items-center justify-center">
                        <img
                          src={sidePreview}
                          alt="Side View"
                          className="max-h-full max-w-full object-contain rounded"
                        />
                        <div className="absolute bottom-1 right-1 bg-emerald-600/90 text-white p-1 rounded-full shadow">
                          <Check className="w-3 h-3" />
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center text-center p-2">
                        <UploadCloud className="w-6 h-6 text-slate-400 group-hover:text-blue-400 transition" />
                        <span className="text-[10px] text-slate-300 font-medium mt-1">
                          Perfil (Dorso/Ventre/Leme)
                        </span>
                        <span className="text-[9px] text-slate-500">Clique ou arraste</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Vista Frontal */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-[11px] font-semibold text-slate-300 flex items-center gap-1">
                    Vista Frontal (Front)
                  </span>
                  <div className="h-32 border-2 border-dashed border-slate-700 hover:border-blue-500/80 rounded-xl bg-slate-950/40 p-2 flex flex-col items-center justify-center relative cursor-pointer group transition overflow-hidden">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={(e) => e.target.files?.[0] && handleSeparateFile('front', e.target.files[0])}
                      className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10"
                    />
                    {frontPreview ? (
                      <div className="relative w-full h-full flex items-center justify-center">
                        <img
                          src={frontPreview}
                          alt="Front View"
                          className="max-h-full max-w-full object-contain rounded"
                        />
                        <div className="absolute bottom-1 right-1 bg-emerald-600/90 text-white p-1 rounded-full shadow">
                          <Check className="w-3 h-3" />
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center text-center p-2">
                        <UploadCloud className="w-6 h-6 text-slate-400 group-hover:text-blue-400 transition" />
                        <span className="text-[10px] text-slate-300 font-medium mt-1">
                          Seção (Diedro/Altura)
                        </span>
                        <span className="text-[9px] text-slate-500">Clique ou arraste</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            /* Upload Area: Mode 2 (Folha Única) */
            <div>
              <div className="border-2 border-dashed border-slate-700 hover:border-blue-500/80 rounded-xl p-4 bg-slate-950/40 flex flex-col items-center justify-center transition cursor-pointer relative min-h-[140px]">
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => e.target.files?.[0] && handleSingleFile(e.target.files[0])}
                  className="absolute inset-0 opacity-0 cursor-pointer w-full h-full z-10"
                />
                {singlePreview ? (
                  <div className="flex flex-col items-center gap-2">
                    <img
                      src={singlePreview}
                      alt="Blueprint Sheet"
                      className="max-h-40 rounded border border-slate-700 object-contain"
                    />
                    <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                      <Check className="w-3.5 h-3.5" /> {singleFile?.name || 'Blueprint Carregada'}
                    </span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-1.5 py-3 text-center">
                    <UploadCloud className="w-8 h-8 text-blue-400" />
                    <span className="text-xs font-medium text-slate-300">
                      Arraste o arquivo da folha de blueprint (3 vistas completas)
                    </span>
                    <span className="text-[10px] text-slate-500">
                      Suporte a PNG, JPG, WEBP de alta resolução
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Gemini API Key Configuration Box */}
          <div className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                <Key className="w-3.5 h-3.5 text-amber-400" /> Google Gemini API Key:
              </label>
              {localApiKey.trim() ? (
                <span className="text-[10px] text-emerald-400 flex items-center gap-1">
                  <Check className="w-3 h-3" /> IA Vision Ativa
                </span>
              ) : (
                <span className="text-[10px] text-amber-400 flex items-center gap-1">
                  <Info className="w-3 h-3" /> Fallback Heurístico Ativo
                </span>
              )}
            </div>
            <input
              type="password"
              placeholder="Cole sua API Key do Google Gemini (ex: AIzaSy...)"
              value={localApiKey}
              onChange={(e) => setLocalApiKey(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 font-mono"
            />
            <p className="text-[10px] text-slate-400">
              O Gemini 2.5 analisa as curvaturas dorsais e ventrais isolando a fuselagem das asas e gerando vértices 3D limpos. Salvo apenas localmente no seu navegador.
            </p>
          </div>

          {/* Presets Bar */}
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-2 flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Dimensões de Referência / Presets:
            </label>
            <div className="grid grid-cols-4 gap-2">
              {PRESETS.map((p) => (
                <button
                  key={p.name}
                  type="button"
                  onClick={() => applyPreset(p)}
                  className={`p-2 rounded-lg border text-left transition flex flex-col justify-between ${
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

          {/* Dimensions Form */}
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="text-[11px] font-semibold text-slate-400 block mb-1">
                Identificação do Modelo / Aeronave
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
              <div className="p-2 rounded-lg bg-slate-800/60 border border-slate-700/60 text-[10px] text-slate-400">
                Padrão Aeronáutico: Nariz em +Z, Cauda em -Z, Asa direita em +X, Topo em +Y.
              </div>
            </div>
          </div>

          {errorMsg && (
            <div className="p-3 rounded-lg bg-red-950/60 border border-red-800/80 text-red-300 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-3.5 border-t border-slate-800 bg-slate-950/70 flex items-center justify-end gap-3">
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
            className="px-5 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-lg transition flex items-center gap-2 disabled:opacity-50"
          >
            {isProcessing ? (
              <>
                <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Reconstruindo com Gemini Vision...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5 text-amber-300" />
                <span>Reconstruir Modelo 3D com IA</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
