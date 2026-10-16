import { create } from 'zustand';
import { BlueprintCalibration, DnmNode, SurfaceMesh } from '@/types';

export type ViewportMode = 'four_quadrants' | 'single_3d' | 'top_only' | 'side_only' | 'front_only';

interface StudioState {
  // Mode & UI
  viewportMode: ViewportMode;
  showWireframe: boolean;
  showGrid: boolean;
  blueprintOpacity: number; // 0.0 to 1.0

  // Calibration
  calibration: BlueprintCalibration | null;
  blueprints: {
    topUrl?: string;
    frontUrl?: string;
    sideUrl?: string;
  };

  // 3D Geometry
  activeMesh: SurfaceMesh | null;
  nodes: Record<string, DnmNode>;
  selectedNodeName: string | null;

  // Animation preview states
  animationValues: Record<number, number>; // CLA channel -> current normalized value 0.0..1.0

  // Actions
  setViewportMode: (mode: ViewportMode) => void;
  setShowWireframe: (show: boolean) => void;
  setShowGrid: (show: boolean) => void;
  setBlueprintOpacity: (opacity: number) => void;
  setCalibration: (calib: BlueprintCalibration) => void;
  setBlueprints: (urls: { topUrl?: string; frontUrl?: string; sideUrl?: string }) => void;
  setActiveMesh: (mesh: SurfaceMesh | null) => void;
  setNodes: (nodes: Record<string, DnmNode>) => void;
  selectNode: (nodeName: string | null) => void;
  setAnimationChannel: (cla: number, value: number) => void;
}

export const useStudioStore = create<StudioState>((set) => ({
  viewportMode: 'four_quadrants',
  showWireframe: false,
  showGrid: true,
  blueprintOpacity: 0.65,

  calibration: null,
  blueprints: {
    topUrl: '/docs/blueprint_top.png',
    frontUrl: '/docs/blueprint_front.png',
    sideUrl: '/docs/blueprint_side.png',
  },

  activeMesh: null,
  nodes: {},
  selectedNodeName: null,
  animationValues: {},

  setViewportMode: (mode) => set({ viewportMode: mode }),
  setShowWireframe: (show) => set({ showWireframe: show }),
  setShowGrid: (show) => set({ showGrid: show }),
  setBlueprintOpacity: (opacity) => set({ blueprintOpacity: opacity }),
  setCalibration: (calib) => set({ calibration: calib }),
  setBlueprints: (urls) =>
    set((state) => ({ blueprints: { ...state.blueprints, ...urls } })),
  setActiveMesh: (mesh) => set({ activeMesh: mesh }),
  setNodes: (nodes) => set({ nodes }),
  selectNode: (nodeName) => set({ selectedNodeName: nodeName }),
  setAnimationChannel: (cla, value) =>
    set((state) => ({
      animationValues: { ...state.animationValues, [cla]: value },
    })),
}));
