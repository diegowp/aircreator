/**
 * Core domain types for AirCreator frontend and 3D studio.
 */

export interface Vector3D {
  x: number;
  y: number;
  z: number;
}

export interface Attitude16 {
  h: number; // Heading (16-bit integer: 0..65535 or -32768..32767)
  p: number; // Pitch (16-bit)
  b: number; // Bank/Roll (16-bit)
}

export interface SurfaceVertex {
  x: number;
  y: number;
  z: number;
  roundShading?: boolean; // 'R' flag in YSFlight .srf
}

export interface SurfaceFace {
  color: [number, number, number]; // RGB 0..255
  color15?: number; // 15-bit packed color
  normal?: Vector3D;
  center?: Vector3D;
  vertexIndices: number[];
  bright?: boolean; // 'B' unshaded flag
}

export interface SurfaceMesh {
  id: string;
  name: string;
  vertices: SurfaceVertex[];
  faces: SurfaceFace[];
  alphaFaces?: { polyIndex: number; alpha: number }[]; // 'ZA' transparency
}

export interface DnmNodeState {
  dx: number;
  dy: number;
  dz: number;
  dh: number;
  dp: number;
  db: number;
  visible: boolean;
}

export interface DnmNode {
  name: string;
  srfFile: string;
  mesh?: SurfaceMesh;
  cla: number; // Animation channel 0..31
  nst: number; // Number of states
  pos: {
    x: number;
    y: number;
    z: number;
    att: Attitude16;
    visible: boolean;
  };
  cnt: Vector3D; // Rotation pivot / hinge center
  rel: 'DEP' | 'IND';
  children: string[];
  states: DnmNodeState[];
}

export interface BlueprintCalibration {
  imageUrl: string;
  scalePixelsPerMeter: number;
  centerlineX: number; // Offset in pixels for X=0
  waterlineY: number; // Offset in pixels for Y=0
  originZ: number; // Offset in pixels for Z=0
  wingspanMeters: number;
  lengthMeters: number;
  heightMeters: number;
}

export interface ComponentMeshDict {
  name: string;
  vertices: [number, number, number][];
  faces: number[][];
  colors: [number, number, number][];
  alphas: number[];
  round_shading: boolean[];
  pivot?: [number, number, number];
  cla?: number;
}

