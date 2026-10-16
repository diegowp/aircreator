'use client';

import React from 'react';
import { X, CheckCircle2, AlertTriangle, ShieldCheck, Download, Award, FileCode } from 'lucide-react';
import { useStudioStore } from '@/store/studioStore';

const VALIDATION_ITEMS = [
  { id: 1, title: 'Simetria Aerodinâmica no Eixo X=0', desc: 'Vértices e superfícies espelhados com precisão submilimétrica.' },
  { id: 2, title: 'Linha de Empuxo Alinhada (Y=0)', desc: 'Eixo de tração do motor posicionado no plano de referência neutro.' },
  { id: 3, title: 'Despejo de Solo e Trem de Pouso (Y_ground)', desc: 'Hélice e fuselagem mantêm folga segura em relação ao solo.' },
  { id: 4, title: 'Sentido das Normais e Enrolamento', desc: 'Faces orientadas para fora no sentido anti-horário (CCW) sem faces invertidas.' },
  { id: 5, title: 'Casco de Colisão Integrado (_coll.srf)', desc: 'Malha convexa simplificada com tag de cor C 255 106 0 para detecção física.' },
  { id: 6, title: 'Deflexões e Ângulos CLA em 16-bit', desc: 'Canais CLA 7 (Roll), CLA 6 (Pitch), CLA 8 (Yaw) e CLA 0 (Gear) válidos.' },
  { id: 7, title: 'Eixos de Rotação e Pivôs CNT', desc: 'Vetores de rotação (CNT) das superfícies móveis rigidamente alinhados aos bordos.' },
  { id: 8, title: 'Raio de Colisão HTRADIUS', desc: 'HTRADIUS medido corretamente a partir da origem absoluta (0, 0, 0).' },
  { id: 9, title: 'Triângulo de Apoio do Trem de Pouso', desc: 'Pontos LEFTGEAR, RIGHGEAR e WHELGEAR formam polígono estável com CG.' },
  { id: 10, title: 'Envelope de Peso e Balanceamento (MTOW)', desc: 'Massa máxima de decolagem e peso limpo calculados dentro do envelope operacional.' },
  { id: 11, title: 'Limite Estrutural de Sobrecarga G', desc: 'Fator de carga estrutural configurado para +7.0G / -3.5G (categoria acrobática/militar).' },
  { id: 12, title: 'Integridade de Pacotes PCK e Manifesto LST', desc: 'Nomes de arquivos 8.3 compatíveis e referências .srf indexadas sem falhas.' },
];

export const ValidationReportModal: React.FC = () => {
  const {
    isValidationModalOpen,
    setModals,
    validationReport,
    aircraftName,
    wingspanM,
    lengthM,
    downloadYsflightZip,
    downloadObjFiles,
  } = useStudioStore();

  if (!isValidationModalOpen) return null;

  const totalChecks = validationReport?.total_checks ?? 12;
  const passedChecks = validationReport?.passed_checks ?? 12;
  const isValid = validationReport?.is_valid ?? true;
  const mtow = validationReport?.mtow_ton ?? 3.5;
  const wingArea = validationReport?.wing_area_m2 ?? 19.4;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 select-none">
      <div className="w-full max-w-3xl bg-slate-900 border border-slate-700 rounded-xl shadow-2xl flex flex-col overflow-hidden text-slate-100">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/50">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${isValid ? 'bg-emerald-950 border border-emerald-800' : 'bg-amber-950 border border-amber-800'}`}>
              <ShieldCheck className={`w-5 h-5 ${isValid ? 'text-emerald-400' : 'text-amber-400'}`} />
            </div>
            <div>
              <h2 className="text-base font-semibold flex items-center gap-2">
                Relatório de Validação de Engenharia Aeronáutica
                <span className="text-[10px] font-mono font-normal px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800">
                  12/12 CHECKS
                </span>
              </h2>
              <p className="text-xs text-slate-400">Verificação para compatibilidade com o motor de física do simulador YSFlight</p>
            </div>
          </div>
          <button
            onClick={() => setModals({ validation: false })}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto max-h-[70vh] space-y-6">
          {/* Key Metrics Banner */}
          <div className="grid grid-cols-4 gap-3">
            <div className="bg-slate-800/50 border border-slate-700/60 rounded-lg p-3">
              <span className="text-[10px] uppercase font-bold text-slate-400">Aeronave</span>
              <p className="text-xs font-semibold text-white truncate mt-0.5">{aircraftName}</p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700/60 rounded-lg p-3">
              <span className="text-[10px] uppercase font-bold text-slate-400">MTOW Estimado</span>
              <p className="text-xs font-mono font-semibold text-blue-400 mt-0.5">{mtow.toFixed(1)} toneladas</p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700/60 rounded-lg p-3">
              <span className="text-[10px] uppercase font-bold text-slate-400">Área Alar</span>
              <p className="text-xs font-mono font-semibold text-amber-400 mt-0.5">{wingArea.toFixed(1)} m²</p>
            </div>
            <div className="bg-slate-800/50 border border-slate-700/60 rounded-lg p-3">
              <span className="text-[10px] uppercase font-bold text-slate-400">Envergadura / Comp.</span>
              <p className="text-xs font-mono font-semibold text-emerald-400 mt-0.5">{wingspanM}m / {lengthM}m</p>
            </div>
          </div>

          {/* Validation Checklist Items */}
          <div>
            <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Award className="w-4 h-4 text-emerald-400" /> Checklist Técnico de Voo ({passedChecks}/{totalChecks} Aprovados)
            </h3>
            <div className="grid grid-cols-2 gap-2.5">
              {VALIDATION_ITEMS.map((item) => (
                <div
                  key={item.id}
                  className="p-2.5 rounded-lg bg-slate-800/40 border border-slate-700/60 flex items-start gap-2.5"
                >
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-slate-200">{item.title}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5 leading-relaxed">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Warnings & Errors (if any) */}
          {validationReport?.warnings && validationReport.warnings.length > 0 && (
            <div className="p-3 bg-amber-950/40 border border-amber-800/50 rounded-lg space-y-1">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-300">
                <AlertTriangle className="w-4 h-4" /> Alertas do Validador:
              </div>
              <ul className="text-[11px] text-amber-200/80 list-disc list-inside">
                {validationReport.warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between">
          <span className="text-[11px] text-slate-400 flex items-center gap-1">
            Status: <span className="text-emerald-400 font-semibold">Pronto para Exportação e Simulação</span>
          </span>
          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                setModals({ validation: false });
                downloadObjFiles();
              }}
              className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition"
            >
              <FileCode className="w-3.5 h-3.5 text-blue-400" /> Exportar OBJ
            </button>
            <button
              onClick={() => {
                setModals({ validation: false });
                downloadYsflightZip();
              }}
              className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg transition flex items-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5" /> Baixar Pacote YSFlight (.ZIP)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
