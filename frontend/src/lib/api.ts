/**
 * AirCreator API Client - Interacts with Python FastAPI backend (http://localhost:8000).
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export interface AircraftPreset {
  id: string;
  category: string;
  propulsion: string;
  default_hp?: number;
  default_thrust_kg?: number;
  has_afterburner: boolean;
}

import { ComponentMeshDict } from '@/types';

export interface ReconstructResponse {
  status: string;
  aircraft_name: string;
  metrics: {
    num_vertices: number;
    num_faces: number;
    wingspan_m: number;
    length_m: number;
    height_m: number;
    centroid: [number, number, number];
    bounding_box: {
      min: [number, number, number];
      max: [number, number, number];
    };
  };
  wing_area_m2: number;
  scale_pixels_per_meter: number;
  components: Record<string, any>;
  component_meshes?: Record<string, ComponentMeshDict>;
  srf_preview?: string;
  full_srf?: string;
}

export interface ValidationReportResponse {
  is_valid: boolean;
  total_checks: number;
  passed_checks: number;
  errors: string[];
  warnings: string[];
  aircraft_id: string;
  mtow_ton: number;
  wing_area_m2: number;
}

export const airCreatorApi = {
  async getPresets(): Promise<AircraftPreset[]> {
    try {
      const res = await fetch(`${API_BASE_URL}/export/presets`);
      if (!res.ok) throw new Error('Falha ao carregar presets');
      return await res.json();
    } catch {
      // Fallback presets if backend is offline
      return [
        { id: 'SUPER_TUCANO', category: 'TRAINER', propulsion: 'TURBOPROP', default_hp: 1600, has_afterburner: false },
        { id: 'TRAINER', category: 'TRAINER', propulsion: 'TURBOPROP', default_hp: 750, has_afterburner: false },
        { id: 'FIGHTER', category: 'FIGHTER', propulsion: 'JET', default_thrust_kg: 8500, has_afterburner: true },
        { id: 'CARGO', category: 'CARGO', propulsion: 'TURBOPROP', default_hp: 4500, has_afterburner: false },
      ];
    }
  },

  async decomposeBlueprint(file?: File, imagePath?: string): Promise<any> {
    const formData = new FormData();
    if (file) {
      formData.append('file', file);
    } else if (imagePath) {
      formData.append('image_path', imagePath);
    }
    formData.append('include_images', 'true');

    const res = await fetch(`${API_BASE_URL}/blueprint/decompose`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Erro ao decompor blueprint' }));
      throw new Error(err.detail || 'Erro ao processar blueprint');
    }
    return await res.json();
  },

  async generateAircraft(params: {
    blueprint_path?: string;
    wingspan_m: number;
    length_m: number;
    height_m: number;
  }): Promise<ReconstructResponse> {
    const res = await fetch(`${API_BASE_URL}/reconstruction/generate-aircraft`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        blueprint_path: params.blueprint_path || 'docs/blueprint.jpg',
        wingspan_m: params.wingspan_m,
        length_m: params.length_m,
        height_m: params.height_m,
        num_fuselage_stations: 18,
        vertices_per_ring: 16,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Erro na reconstrução 3D' }));
      throw new Error(err.detail || 'Erro ao reconstruir aeronave');
    }
    return await res.json();
  },

  async validateModel(params: {
    aircraft_name: string;
    blueprint_path?: string;
    preset_name: string;
    wingspan_m: number;
    length_m: number;
    height_m: number;
  }): Promise<ValidationReportResponse> {
    const res = await fetch(`${API_BASE_URL}/export/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error('Erro ao validar modelo');
    return await res.json();
  },

  async downloadYsflightZip(params: {
    aircraft_name: string;
    blueprint_path?: string;
    preset_name: string;
    wingspan_m: number;
    length_m: number;
    height_m: number;
  }): Promise<Blob> {
    const res = await fetch(`${API_BASE_URL}/export/ysflight-zip`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error('Erro ao gerar pacote ZIP');
    return await res.blob();
  },

  async downloadObj(params: {
    aircraft_name: string;
    blueprint_path?: string;
    preset_name: string;
    wingspan_m: number;
    length_m: number;
    height_m: number;
  }): Promise<{ obj: string; mtl: string; aircraft_id: string }> {
    const res = await fetch(`${API_BASE_URL}/export/obj`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    });
    if (!res.ok) throw new Error('Erro ao exportar OBJ');
    return await res.json();
  },
};
