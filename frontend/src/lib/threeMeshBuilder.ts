import * as THREE from 'three';
import { ComponentMeshDict } from '@/types';
import { ReconstructResponse } from '@/lib/api';

export interface AircraftMeshScene {
  rootGroup: THREE.Group;
  parts: Record<string, THREE.Mesh | THREE.Group>;
  hingePivots: Record<string, THREE.Group>;
}

export function buildAircraftSceneFromApi(reconstructData: ReconstructResponse): AircraftMeshScene {
  const rootGroup = new THREE.Group();
  rootGroup.name = 'aircraft_root';

  const parts: Record<string, THREE.Mesh | THREE.Group> = {};
  const hingePivots: Record<string, THREE.Group> = {};

  const componentMeshes = reconstructData.component_meshes;
  if (!componentMeshes || Object.keys(componentMeshes).length === 0) {
    return createProceduralSuperTucanoScene();
  }

  // Materials
  const fuselageMat = new THREE.MeshStandardMaterial({
    color: 0xf1f5f9,
    roughness: 0.35,
    metalness: 0.15,
    side: THREE.DoubleSide,
  });

  const wingMat = new THREE.MeshStandardMaterial({
    color: 0xeab308,
    roughness: 0.3,
    metalness: 0.2,
    side: THREE.DoubleSide,
  });

  const tailMat = new THREE.MeshStandardMaterial({
    color: 0xf1f5f9,
    roughness: 0.35,
    metalness: 0.15,
    side: THREE.DoubleSide,
  });

  const darkMat = new THREE.MeshStandardMaterial({
    color: 0x1e293b,
    roughness: 0.45,
    metalness: 0.25,
    side: THREE.DoubleSide,
  });

  const canopyMat = new THREE.MeshPhysicalMaterial({
    color: 0x38bdf8,
    transparent: true,
    opacity: 0.55,
    roughness: 0.1,
    transmission: 0.75,
    thickness: 0.25,
    side: THREE.DoubleSide,
    depthWrite: false,
  });

  for (const [compName, comp] of Object.entries(componentMeshes)) {
    if (!comp.vertices || comp.vertices.length === 0 || !comp.faces || comp.faces.length === 0) {
      continue;
    }

    const geom = new THREE.BufferGeometry();
    const positions: number[] = [];
    const indices: number[] = [];

    // Push all vertices
    for (const v of comp.vertices) {
      positions.push(v[0], v[1], v[2]);
    }
    geom.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));

    // Triangulate faces
    for (const face of comp.faces) {
      if (face.length < 3) continue;
      for (let j = 1; j < face.length - 1; j++) {
        indices.push(face[0], face[j], face[j + 1]);
      }
    }
    geom.setIndex(indices);
    geom.computeVertexNormals();

    // Select material
    let mat: THREE.Material = fuselageMat;
    if (compName.startsWith('wing') || compName.startsWith('aileron')) {
      mat = wingMat;
    } else if (compName.startsWith('elevator') || compName.startsWith('rudder')) {
      mat = tailMat;
    } else if (compName === 'canopy') {
      mat = canopyMat;
    } else if (compName === 'helice' || compName === 'propeller') {
      mat = darkMat;
    }

    const mesh = new THREE.Mesh(geom, mat);
    mesh.name = `${compName}_mesh`;
    mesh.castShadow = true;
    mesh.receiveShadow = true;

    // Check if movable hinge pivot
    const pivot = comp.pivot;
    const isMovable =
      (comp.cla !== undefined && comp.cla > 0) ||
      compName.includes('aileron') ||
      compName.includes('elevator') ||
      compName.includes('rudder') ||
      compName.includes('helice');

    if (pivot && isMovable) {
      const [px, py, pz] = pivot;
      const pivotGroup = new THREE.Group();
      pivotGroup.name = compName;
      pivotGroup.position.set(px, py, pz);

      // Offset mesh so its local origin is at the hinge pivot
      mesh.position.set(-px, -py, -pz);
      pivotGroup.add(mesh);

      hingePivots[compName] = pivotGroup;
      parts[compName] = pivotGroup;
      rootGroup.add(pivotGroup);
    } else {
      mesh.name = compName;
      parts[compName] = mesh;
      rootGroup.add(mesh);
    }
  }

  return { rootGroup, parts, hingePivots };
}


export function createProceduralSuperTucanoScene(): AircraftMeshScene {
  const rootGroup = new THREE.Group();
  rootGroup.name = 'aircraft_root';

  const parts: Record<string, THREE.Mesh | THREE.Group> = {};
  const hingePivots: Record<string, THREE.Group> = {};

  // Materials
  const fuselageMat = new THREE.MeshStandardMaterial({
    color: 0xf1f5f9, // Clean white
    roughness: 0.35,
    metalness: 0.15,
  });

  const wingMat = new THREE.MeshStandardMaterial({
    color: 0xeab308, // Golden yellow (T-25 & FAB Tucano style)
    roughness: 0.3,
    metalness: 0.2,
  });

  const darkMat = new THREE.MeshStandardMaterial({
    color: 0x1e293b, // Dark navy anti-glare panel & spinner
    roughness: 0.5,
    metalness: 0.3,
  });

  const canopyMat = new THREE.MeshPhysicalMaterial({
    color: 0x38bdf8,
    transparent: true,
    opacity: 0.55,
    roughness: 0.1,
    transmission: 0.7,
    thickness: 0.2,
  });

  // 1. Fuselage
  // In Three.js: +X Right, +Y Up, -Z Forward (or +Z Forward with camera adjusted)
  // We model aligned to aircraft standard: Nose pointing towards -Z
  const fuselageGroup = new THREE.Group();
  fuselageGroup.name = 'fuselagem';

  const fuseGeom = new THREE.CylinderGeometry(0.55, 0.25, 9.8, 16, 8);
  fuseGeom.rotateX(Math.PI / 2);
  fuseGeom.scale(1.0, 1.25, 1.0); // Slightly taller than wide
  const fuseMesh = new THREE.Mesh(fuseGeom, fuselageMat);
  fuseMesh.position.set(0, 0.4, 0);
  fuselageGroup.add(fuseMesh);

  // Nose Cone (Spinner)
  const spinnerGeom = new THREE.ConeGeometry(0.48, 1.4, 16);
  spinnerGeom.rotateX(-Math.PI / 2);
  const spinnerMesh = new THREE.Mesh(spinnerGeom, darkMat);
  spinnerMesh.position.set(0, 0.35, 5.5);
  fuselageGroup.add(spinnerMesh);

  // Cockpit Canopy (Transparent Bubble)
  const canopyGeom = new THREE.SphereGeometry(0.7, 16, 12);
  canopyGeom.scale(0.75, 0.85, 2.4);
  const canopyMesh = new THREE.Mesh(canopyGeom, canopyMat);
  canopyMesh.position.set(0, 1.0, 1.2);
  fuselageGroup.add(canopyMesh);

  rootGroup.add(fuselageGroup);
  parts['fuselagem'] = fuselageGroup;

  // 2. Right Wing (Starboard)
  const wingRGroup = new THREE.Group();
  wingRGroup.name = 'wing_r';
  const wingGeomR = new THREE.BoxGeometry(4.8, 0.18, 1.8);
  wingGeomR.translate(2.7, 0, -0.2);
  // Slight dihedral
  wingGeomR.rotateZ(0.06);
  const wingMeshR = new THREE.Mesh(wingGeomR, wingMat);
  wingMeshR.position.set(0, 0.1, 0.4);
  wingRGroup.add(wingMeshR);

  // Aileron Right (Mounted on a hinge pivot)
  const aileronPivotR = new THREE.Group();
  aileronPivotR.position.set(3.5, 0.2, -0.6); // Hinge line location
  const aileronGeomR = new THREE.BoxGeometry(1.8, 0.12, 0.45);
  aileronGeomR.translate(0, 0, -0.22);
  const aileronMeshR = new THREE.Mesh(aileronGeomR, wingMat);
  aileronPivotR.add(aileronMeshR);
  wingRGroup.add(aileronPivotR);

  hingePivots['aileron_d'] = aileronPivotR;
  parts['wing_r'] = wingRGroup;
  parts['aileron_d'] = aileronPivotR;
  rootGroup.add(wingRGroup);

  // 3. Left Wing (Port)
  const wingLGroup = new THREE.Group();
  wingLGroup.name = 'wing_l';
  const wingGeomL = new THREE.BoxGeometry(4.8, 0.18, 1.8);
  wingGeomL.translate(-2.7, 0, -0.2);
  wingGeomL.rotateZ(-0.06);
  const wingMeshL = new THREE.Mesh(wingGeomL, wingMat);
  wingMeshL.position.set(0, 0.1, 0.4);
  wingLGroup.add(wingMeshL);

  // Aileron Left (Hinge pivot)
  const aileronPivotL = new THREE.Group();
  aileronPivotL.position.set(-3.5, 0.2, -0.6);
  const aileronGeomL = new THREE.BoxGeometry(1.8, 0.12, 0.45);
  aileronGeomL.translate(0, 0, -0.22);
  const aileronMeshL = new THREE.Mesh(aileronGeomL, wingMat);
  aileronPivotL.add(aileronMeshL);
  wingLGroup.add(aileronPivotL);

  hingePivots['aileron_lef'] = aileronPivotL;
  parts['wing_l'] = wingLGroup;
  parts['aileron_lef'] = aileronPivotL;
  rootGroup.add(wingLGroup);

  // 4. Horizontal Stabilizer & Elevator
  const hStabGroup = new THREE.Group();
  hStabGroup.name = 'elevator_1';
  const hStabGeom = new THREE.BoxGeometry(3.6, 0.12, 1.0);
  hStabGeom.translate(0, 0.45, -4.2);
  const hStabMesh = new THREE.Mesh(hStabGeom, fuselageMat);
  hStabGroup.add(hStabMesh);

  // Movable Elevator
  const elevatorPivot = new THREE.Group();
  elevatorPivot.position.set(0, 0.45, -4.7);
  const elevatorGeom = new THREE.BoxGeometry(3.4, 0.09, 0.38);
  elevatorGeom.translate(0, 0, -0.19);
  const elevatorMesh = new THREE.Mesh(elevatorGeom, fuselageMat);
  elevatorPivot.add(elevatorMesh);
  hStabGroup.add(elevatorPivot);

  hingePivots['elevator'] = elevatorPivot;
  parts['elevator_1'] = hStabGroup;
  parts['elevator'] = elevatorPivot;
  rootGroup.add(hStabGroup);

  // 5. Vertical Stabilizer & Rudder
  const vFinGroup = new THREE.Group();
  vFinGroup.name = 'rudder_1';
  const vFinGeom = new THREE.BoxGeometry(0.12, 2.2, 1.4);
  vFinGeom.translate(0, 1.4, -4.2);
  const vFinMesh = new THREE.Mesh(vFinGeom, fuselageMat);
  vFinGroup.add(vFinMesh);

  // Movable Rudder
  const rudderPivot = new THREE.Group();
  rudderPivot.position.set(0, 1.4, -4.9);
  const rudderGeom = new THREE.BoxGeometry(0.10, 1.9, 0.45);
  rudderGeom.translate(0, 0, -0.22);
  const rudderMesh = new THREE.Mesh(rudderGeom, fuselageMat);
  rudderPivot.add(rudderMesh);
  vFinGroup.add(rudderPivot);

  hingePivots['rudder_2'] = rudderPivot;
  parts['rudder_1'] = vFinGroup;
  parts['rudder_2'] = rudderPivot;
  rootGroup.add(vFinGroup);

  // 6. 5-Blade Propeller (CLA 18)
  const propGroup = new THREE.Group();
  propGroup.name = 'helice';
  propGroup.position.set(0, 0.35, 6.2);

  const numBlades = 5;
  for (let b = 0; b < numBlades; b++) {
    const angle = (b * 2 * Math.PI) / numBlades;
    const bladeGeom = new THREE.BoxGeometry(0.12, 1.25, 0.02);
    bladeGeom.translate(0, 0.65, 0);
    bladeGeom.rotateZ(angle);
    const bladeMesh = new THREE.Mesh(bladeGeom, darkMat);
    propGroup.add(bladeMesh);
  }
  rootGroup.add(propGroup);
  parts['helice'] = propGroup;

  return { rootGroup, parts, hingePivots };
}

export function updateAircraftKinematics(
  scene: AircraftMeshScene,
  animationValues: Record<number, number>
) {
  // CLA 7: Ailerons (Roll: -1.0 to +1.0)
  const aileronVal = animationValues[7] ?? 0;
  const maxAileronRad = THREE.MathUtils.degToRad(15);
  if (scene.hingePivots['aileron_d']) {
    scene.hingePivots['aileron_d'].rotation.x = aileronVal * maxAileronRad;
  }
  if (scene.hingePivots['aileron_lef']) {
    // Opposite deflection
    scene.hingePivots['aileron_lef'].rotation.x = -aileronVal * maxAileronRad;
  }

  // CLA 6: Elevator (Pitch: -1.0 to +1.0)
  const elevatorVal = animationValues[6] ?? 0;
  const maxElevRad = THREE.MathUtils.degToRad(18);
  if (scene.hingePivots['elevator']) {
    scene.hingePivots['elevator'].rotation.x = -elevatorVal * maxElevRad;
  }

  // CLA 8: Rudder (Yaw: -1.0 to +1.0)
  const rudderVal = animationValues[8] ?? 0;
  const maxRudderRad = THREE.MathUtils.degToRad(25);
  if (scene.hingePivots['rudder_2']) {
    scene.hingePivots['rudder_2'].rotation.y = -rudderVal * maxRudderRad;
  }

  // CLA 3 / Propeller spin
  if (scene.parts['helice']) {
    scene.parts['helice'].rotation.z += 0.08;
  }
}
