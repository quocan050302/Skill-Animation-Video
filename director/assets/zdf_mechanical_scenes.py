"""Modular Mechanical Systems & Layered Cutaway 3D Rigs (ZDF Only)."""

from __future__ import annotations


MECHANICAL_SYSTEMS_JS = r"""import * as THREE from 'three';
import { materials } from './materials.js';
import { LayeredCutaway } from './layered_cutaway.js';
import { clamp, lerp, smooth } from './anim.js';

function shadow(o) {
  o.traverse(c => { if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } });
  return o;
}

function makeDisplayTexture(topText, mainText, accent = '#38bdf8', bg = '#0f172a') {
  const c = document.createElement('canvas');
  c.width = 256; c.height = 160;
  const ctx = c.getContext('2d');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, 256, 160);
  ctx.strokeStyle = accent;
  ctx.lineWidth = 6;
  ctx.strokeRect(8, 8, 240, 144);
  ctx.textAlign = 'center';
  ctx.fillStyle = '#94a3b8';
  ctx.font = '700 22px sans-serif';
  ctx.fillText(topText, 128, 48);
  ctx.fillStyle = accent;
  ctx.font = '700 54px sans-serif';
  ctx.fillText(mainText, 128, 118);
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/**
 * 1. Physical Lobby Wall & Tactile Call Button Panel (button surface at [0.24, 1.16, 0.24], normal [-1,0,0]).
 */
export function makePushButtonPanelRig() {
  const M = materials();
  const g = new THREE.Group();

  // Lobby tiled wall section + floor plinth behind panel
  const wallMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.78, metalness: 0.06 });
  const wall = new THREE.Mesh(new THREE.BoxGeometry(0.28, 2.35, 1.35), wallMat);
  wall.position.set(0.41, 1.175, 0.10);
  g.add(wall);

  // Dark steel trim band along wall
  const trim = new THREE.Mesh(new THREE.BoxGeometry(0.29, 0.08, 1.36), M.steelDark);
  trim.position.set(0.41, 0.04, 0.10);
  g.add(trim);

  // Brushed stainless faceplate mounted on lobby wall facing -X
  const plateMat = new THREE.MeshPhysicalMaterial({ color: 0xd1d5db, metalness: 0.90, roughness: 0.26, clearcoat: 0.25 });
  const plate = new THREE.Mesh(new THREE.BoxGeometry(0.022, 0.34, 0.20), plateMat);
  plate.position.set(0.268, 1.18, 0.24);
  g.add(plate);

  // Outer recessed bezel housing around call button
  const bezel = new THREE.Mesh(new THREE.CylinderGeometry(0.036, 0.040, 0.018, 32), M.steelDark);
  bezel.rotation.z = Math.PI / 2;
  bezel.position.set(0.252, 1.16, 0.24);
  g.add(bezel);

  // Illuminated LED ring around button plunger
  const haloMat = new THREE.MeshStandardMaterial({
    color: 0x38bdf8, emissive: 0xf59e0b, emissiveIntensity: 0.12, roughness: 0.25
  });
  const halo = new THREE.Mesh(new THREE.TorusGeometry(0.031, 0.0045, 12, 32), haloMat);
  halo.rotation.y = Math.PI / 2;
  halo.position.set(0.247, 1.16, 0.24);
  g.add(halo);

  // Physical moving button plunger: resting front face at x = 0.240, y = 1.16, z = 0.24
  const plungerMat = new THREE.MeshPhysicalMaterial({
    color: 0xf8fafc, emissive: 0xf59e0b, emissiveIntensity: 0.08, roughness: 0.22, metalness: 0.15, clearcoat: 0.6
  });
  const plunger = new THREE.Mesh(new THREE.CylinderGeometry(0.026, 0.026, 0.024, 32), plungerMat);
  plunger.rotation.z = Math.PI / 2;
  plunger.position.set(0.252, 1.16, 0.24); // front cap sits at 0.252 - 0.012 = 0.240
  g.add(plunger);

  // Small up-arrow indicator LED above button
  const displayMat = new THREE.MeshStandardMaterial({
    map: makeDisplayTexture('CALL', 'UP ▲', '#38bdf8'), emissive: 0x0ea5e9, emissiveIntensity: 0.35, roughness: 0.3
  });
  const display = new THREE.Mesh(new THREE.PlaneGeometry(0.11, 0.07), displayMat);
  display.rotation.y = -Math.PI / 2;
  display.position.set(0.256, 1.28, 0.24);
  g.add(display);

  g.setButtonState = (depressM, lit) => {
    plunger.position.x = 0.252 + Math.max(0, Math.min(0.012, depressM));
    haloMat.emissive.setHex(lit ? 0xf59e0b : 0x38bdf8);
    haloMat.emissiveIntensity = lit ? 2.2 : 0.18;
    plungerMat.emissiveIntensity = lit ? 0.95 : 0.05;
  };
  g.buttonSurfaceWorld = [0.24, 1.16, 0.24];
  g.buttonNormal = [-1, 0, 0];
  return shadow(g);
}

/**
 * 2. LayeredCutaway Controller Cabinet: outer steel housing + hinged door + DIN rail + logic PCB + relays + wiring.
 */
export function makeControllerCabinetRig() {
  const M = materials();
  const cutaway = new LayeredCutaway({
    id: 'controller_cabinet_cutaway',
    worldAnchor: [0, 1.24, 0.06],
    clipNormal: [0, 0, -1],
    clipConstantStart: 0.24,
    clipConstantOpen: 0.03,
  });

  const cabMat = new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.72, roughness: 0.36 });
  const doorMat = new THREE.MeshPhysicalMaterial({ color: 0x475569, metalness: 0.78, roughness: 0.30, clearcoat: 0.2 });

  // Outer rear box + side walls (clipped smoothly on front +Z face during cutaway reveal)
  const backBox = new THREE.Group();
  const backWall = new THREE.Mesh(new THREE.BoxGeometry(0.66, 0.78, 0.03), cabMat);
  backWall.position.set(0, 1.24, -0.10);
  const topCap = new THREE.Mesh(new THREE.BoxGeometry(0.66, 0.03, 0.24), cabMat);
  topCap.position.set(0, 1.62, 0.01);
  const botCap = new THREE.Mesh(new THREE.BoxGeometry(0.66, 0.03, 0.24), cabMat);
  botCap.position.set(0, 0.86, 0.01);
  const leftWall = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.78, 0.24), cabMat);
  leftWall.position.set(-0.315, 1.24, 0.01);
  const rightWall = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.78, 0.24), cabMat);
  rightWall.position.set(0.315, 1.24, 0.01);
  backBox.add(backWall, topCap, botCap, leftWall, rightWall);
  cutaway.addInternalComponent('cabinet_frame', backBox, { layerIndex: 0, materialId: 'mat_cabinet_steel' });

  // Hinged front cabinet door (pivots around left hinge at x=-0.315, z=0.13)
  const doorPivot = new THREE.Group();
  doorPivot.position.set(-0.315, 1.24, 0.135);
  const doorMesh = new THREE.Mesh(new THREE.BoxGeometry(0.64, 0.74, 0.022), doorMat);
  doorMesh.position.set(0.32, 0, 0);
  const hazardBadge = new THREE.Mesh(
    new THREE.PlaneGeometry(0.24, 0.15),
    new THREE.MeshStandardMaterial({ map: makeDisplayTexture('LOGIC', 'CTRL', '#f59e0b', '#1e293b'), roughness: 0.4 })
  );
  hazardBadge.position.set(0.32, 0.12, 0.013);
  doorPivot.add(doorMesh, hazardBadge);
  cutaway.addOuterShell(doorPivot, { applyClip: false });

  // Layer 1: DIN mounting rail + logic PCB board
  const dinRail = new THREE.Mesh(new THREE.BoxGeometry(0.54, 0.045, 0.018), M.steelBright);
  dinRail.position.set(0, 1.24, -0.065);
  cutaway.addInternalComponent('din_rail', dinRail, { layerIndex: 1, materialId: 'mat_steel_bright' });

  const pcbMat = new THREE.MeshStandardMaterial({ color: 0x0f5132, roughness: 0.42, metalness: 0.25 });
  const pcb = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.56, 0.016), pcbMat);
  pcb.position.set(0, 1.24, -0.035);
  cutaway.addInternalComponent('controller_pcb', pcb, { layerIndex: 2, materialId: 'mat_pcb_green' });

  // Layer 2: Microprocessor IC + terminal block + 3 actuated relays
  const cpuMat = new THREE.MeshPhysicalMaterial({ color: 0x111827, roughness: 0.25, metalness: 0.35, clearcoat: 0.6 });
  const cpu = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.14, 0.022), cpuMat);
  cpu.position.set(-0.08, 1.32, -0.015);
  cutaway.addInternalComponent('logic_microcontroller', cpu, { layerIndex: 3, materialId: 'mat_cpu_ic' });

  const relays = [];
  const relayLeds = [];
  for (let k = 0; k < 3; k++) {
    const ry = 1.40 - k * 0.16;
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.09, 0.045), new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.35 }));
    body.position.set(0.12, ry, -0.005);
    const arm = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.016, 0.016), M.copper);
    arm.position.set(0.075, ry, 0.022);
    const ledMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x22c55e, emissiveIntensity: 0.15 });
    const led = new THREE.Mesh(new THREE.SphereGeometry(0.014, 14, 10), ledMat);
    led.position.set(0.16, ry + 0.025, 0.022);
    cutaway.addInternalComponent('relay_' + k, body, { layerIndex: 3 });
    cutaway.internalGroup.add(arm, led);
    relays.push(arm);
    relayLeds.push(ledMat);
  }

  // Layer 3: Copper input & drive-output wiring harnesses with moving signal pulses
  cutaway.addConnectionEdge('button_input_harness', [[-0.28, 1.00, 0.02], [-0.18, 1.15, 0.01], [-0.08, 1.30, 0.01]], 0.009, 0xf59e0b);
  cutaway.addConnectionEdge('relay_bus_harness', [[-0.08, 1.32, 0.01], [0.04, 1.34, 0.015], [0.12, 1.24, 0.015], [0.22, 1.02, 0.01]], 0.009, 0x38bdf8);
  for (let i = 0; i < 4; i++) {
    cutaway.addFlowPulseOnEdge(0, 0xfbbf24, 0.015, i * 0.25);
    cutaway.addFlowPulseOnEdge(1, 0x38bdf8, 0.015, i * 0.25);
  }

  cutaway.updateCabinet = (lt, dur) => {
    const u = clamp(lt / Math.max(0.2, dur), 0, 1);
    const openU = smooth(clamp(u * 2.2, 0, 1));
    cutaway.setReveal(openU, { hingeRotY: -1.65 });
    cutaway.updateFlow(lt, 1.25);
    relays.forEach((arm, k) => {
      const latchT = 0.28 + k * 0.18;
      const engaged = u >= latchT ? 1.0 : 0.0;
      arm.rotation.z = lerp(0.25, -0.05, engaged);
      relayLeds[k].emissiveIntensity = engaged > 0.5 ? (1.4 + 0.4 * Math.sin(lt * 8 + k)) : 0.12;
    });
  };
  return shadow(cutaway.root), cutaway;
}

/**
 * 3. LayeredCutaway Traction Machine Room: cutaway motor housing, spinning rotor, grooved traction sheave, brake calipers & steel ropes.
 */
export function makeTractionDriveMachineRig() {
  const M = materials();
  const cutaway = new LayeredCutaway({
    id: 'traction_machine_room',
    worldAnchor: [0.06, 1.28, 0.0],
    clipNormal: [0, 0, -1],
    clipConstantStart: 0.35,
    clipConstantOpen: 0.02,
  });

  // Structural steel machine room bedplate
  const bed = new THREE.Mesh(new THREE.BoxGeometry(1.52, 0.16, 0.92), M.steelDark);
  bed.position.set(0, 0.84, 0);
  const legL = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.76, 0.72), M.steelDark);
  legL.position.set(-0.56, 0.38, 0);
  const legR = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.76, 0.72), M.steelDark);
  legR.position.set(0.56, 0.38, 0);
  cutaway.addInternalComponent('machine_bedplate', bed, { layerIndex: 0 });
  cutaway.internalGroup.add(legL, legR);

  // Outer ribbed motor stator housing (clipped cleanly so copper windings & spinning rotor show inside!)
  const housingGroup = new THREE.Group();
  const outerCyl = new THREE.Mesh(
    new THREE.CylinderGeometry(0.32, 0.32, 0.62, 32),
    new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.75, roughness: 0.35 })
  );
  outerCyl.rotation.z = Math.PI / 2;
  outerCyl.position.set(-0.34, 1.28, 0);
  housingGroup.add(outerCyl);
  cutaway.addOuterShell(housingGroup, { applyClip: true });

  // Internal stator copper windings + spinning rotor & main drive shaft
  const statorGroup = new THREE.Group();
  for (let k = 0; k < 8; k++) {
    const a = (k / 8) * Math.PI * 2;
    const coil = new THREE.Mesh(new THREE.BoxGeometry(0.46, 0.075, 0.075), M.copper);
    coil.position.set(-0.34, 1.28 + Math.cos(a) * 0.22, Math.sin(a) * 0.22);
    coil.rotation.x = a;
    statorGroup.add(coil);
  }
  cutaway.addInternalComponent('motor_copper_stator', statorGroup, { layerIndex: 1 });

  const rotorGroup = new THREE.Group();
  rotorGroup.position.set(-0.34, 1.28, 0);
  const rotorCore = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.15, 0.50, 24), M.steelBright);
  rotorCore.rotation.z = Math.PI / 2;
  const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.055, 0.055, 1.18, 24), M.steelBright);
  shaft.rotation.z = Math.PI / 2;
  shaft.position.x = 0.34;
  rotorGroup.add(rotorCore, shaft);
  cutaway.addInternalComponent('motor_rotor_shaft', rotorGroup, { layerIndex: 2 });

  // Large grooved traction sheave on +X end of drive shaft
  const sheaveGroup = new THREE.Group();
  sheaveGroup.position.set(0.34, 1.28, 0);
  const sheaveDisc = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.36, 0.14, 36), M.steel);
  sheaveDisc.rotation.z = Math.PI / 2;
  sheaveGroup.add(sheaveDisc);
  for (let g = -1; g <= 1; g++) {
    const groove = new THREE.Mesh(new THREE.TorusGeometry(0.355, 0.012, 10, 40), M.steelDark);
    groove.rotation.y = Math.PI / 2;
    groove.position.x = g * 0.04;
    sheaveGroup.add(groove);
  }
  for (let sp = 0; sp < 6; sp++) {
    const bolt = new THREE.Mesh(new THREE.CylinderGeometry(0.022, 0.022, 0.16, 12), M.copper);
    bolt.rotation.z = Math.PI / 2;
    const ang = (sp / 6) * Math.PI * 2;
    bolt.position.set(0, Math.cos(ang) * 0.18, Math.sin(ang) * 0.18);
    sheaveGroup.add(bolt);
  }
  cutaway.addInternalComponent('traction_sheave', sheaveGroup, { layerIndex: 2 });

  // Brake caliper pads straddling brake drum on shaft
  const caliperTop = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.08, 0.22), new THREE.MeshStandardMaterial({ color: 0xdc2626, roughness: 0.4, metalness: 0.4 }));
  caliperTop.position.set(0.02, 1.44, 0);
  cutaway.addInternalComponent('brake_caliper', caliperTop, { layerIndex: 2 });

  // Steel hoist ropes dropping down both sides of sheave
  const ropeMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.85, roughness: 0.35 });
  for (const g of [-1, 1]) {
    const ropeCar = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 1.30, 10), ropeMat);
    ropeCar.position.set(0.34 + g * 0.04, 0.64, -0.35);
    const ropeCw = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 1.30, 10), ropeMat);
    ropeCw.position.set(0.34 + g * 0.04, 0.64, 0.35);
    cutaway.internalGroup.add(ropeCar, ropeCw);
  }

  cutaway.addConnectionEdge('motor_power_conduit', [[-0.65, 1.00, 0.22], [-0.45, 1.12, 0.18], [-0.34, 1.24, 0.12]], 0.012, 0xf59e0b);
  cutaway.addFlowPulseOnEdge(0, 0xfbbf24, 0.020, 0.0);
  cutaway.addFlowPulseOnEdge(0, 0xfbbf24, 0.020, 0.5);

  cutaway.updateDrive = (lt, dur, { decelerate = false } = {}) => {
    const u = clamp(lt / Math.max(0.2, dur), 0, 1);
    cutaway.setReveal(smooth(clamp(u * 2.4, 0, 1)));
    cutaway.updateFlow(lt, decelerate ? 0.5 : 1.4);
    const angle = decelerate
      ? (lt * 4.5 * (1.0 - 0.55 * u))
      : (lt * (2.5 + 4.5 * smooth(u)));
    rotorGroup.rotation.x = angle;
    sheaveGroup.rotation.x = angle;
    // Caliper lifts open while running, clamps when slowing near end
    const brakeOpen = decelerate ? (1.0 - smooth(clamp((u - 0.55) / 0.45, 0, 1))) : smooth(clamp(u * 3.0, 0, 1));
    caliperTop.position.y = 1.38 + 0.07 * brakeOpen;
  };
  return shadow(cutaway.root), cutaway;
}

/**
 * 4. LayeredCutaway Elevator Shaft: guide rails, cabin + counterweight moving in opposite directions, floor position sensors.
 */
export function makeElevatorShaftRig() {
  const M = materials();
  const cutaway = new LayeredCutaway({
    id: 'elevator_shaft_cutaway',
    worldAnchor: [0.0, 1.24, 0.04],
    clipNormal: [0, 0, -1],
    clipConstantStart: 0.42,
    clipConstantOpen: -0.05,
  });

  // Cutaway structural hoistway framing & translucent front safety glass
  const wallMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.85, metalness: 0.25 });
  const backShaft = new THREE.Mesh(new THREE.BoxGeometry(1.65, 2.65, 0.08), wallMat);
  backShaft.position.set(0, 1.325, -0.34);
  cutaway.addInternalComponent('shaft_back_wall', backShaft, { layerIndex: 0 });

  const glassWall = new THREE.Mesh(
    new THREE.BoxGeometry(1.56, 2.55, 0.02),
    new THREE.MeshPhysicalMaterial({ color: 0x93c5fd, transparent: true, opacity: 0.24, roughness: 0.12, metalness: 0.05 })
  );
  glassWall.position.set(0, 1.32, 0.34);
  cutaway.addOuterShell(glassWall, { applyClip: true });

  // Guide rails + top overhead sheave wheel inside shaft
  for (const rx of [-0.66, 0.14, 0.26, 0.68]) {
    const rail = new THREE.Mesh(new THREE.BoxGeometry(0.045, 2.56, 0.045), M.steelBright);
    rail.position.set(rx, 1.28, -0.04);
    cutaway.internalGroup.add(rail);
  }
  const topSheave = new THREE.Mesh(new THREE.CylinderGeometry(0.24, 0.24, 0.10, 32), M.steel);
  topSheave.rotation.x = Math.PI / 2;
  topSheave.position.set(0.08, 2.38, -0.04);
  cutaway.addInternalComponent('top_sheave', topSheave, { layerIndex: 1 });

  // Passenger Elevator Car on left bay (x = -0.26)
  const carGroup = new THREE.Group();
  carGroup.position.set(-0.26, 0.55, 0.0);
  const carFrame = new THREE.Mesh(new THREE.BoxGeometry(0.68, 0.84, 0.52), M.steelBright);
  const carInterior = new THREE.Mesh(
    new THREE.BoxGeometry(0.56, 0.68, 0.54),
    new THREE.MeshStandardMaterial({ color: 0xfef3c7, emissive: 0xfde68a, emissiveIntensity: 0.38, roughness: 0.45 })
  );
  carGroup.add(carFrame, carInterior);
  cutaway.addInternalComponent('elevator_car', carGroup, { layerIndex: 2, materialId: 'mat_car_steel' });

  // Steel Counterweight on right bay (x = +0.47) moving OPPOSITE to car!
  const cwGroup = new THREE.Group();
  cwGroup.position.set(0.47, 1.92, -0.02);
  const cwFrame = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.72, 0.18), M.steelDark);
  for (let b = -2; b <= 2; b++) {
    const block = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.09, 0.20), M.copper);
    block.position.y = b * 0.125;
    cwGroup.add(block);
  }
  cwGroup.add(cwFrame);
  cutaway.addInternalComponent('counterweight_frame', cwGroup, { layerIndex: 2, materialId: 'mat_counterweight' });

  // Dynamic hoist ropes linking car <-> topSheave <-> counterweight
  const ropeMat = new THREE.MeshStandardMaterial({ color: 0xcbd5e1, metalness: 0.88, roughness: 0.28 });
  const ropeCar = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1.0, 10), ropeMat);
  const ropeCw = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1.0, 10), ropeMat);
  cutaway.internalGroup.add(ropeCar, ropeCw);

  // Floor position magnetic vane sensors mounted on rail + signal conduit bus
  const sensors = [];
  for (let f = 0; f < 3; f++) {
    const sy = 0.65 + f * 0.62;
    const sMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0x22c55e, emissiveIntensity: 0.15 });
    const sens = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.06, 0.06), sMat);
    sens.position.set(0.12, sy, 0.06);
    cutaway.addInternalComponent('floor_sensor_' + f, sens, { layerIndex: 1 });
    sensors.push({ mesh: sens, mat: sMat, y: sy });
  }
  cutaway.addConnectionEdge('sensor_signal_bus', [[0.14, 0.55, 0.06], [0.14, 1.35, 0.06], [0.14, 2.34, 0.06]], 0.008, 0x0ea5e9);
  cutaway.addFlowPulseOnEdge(0, 0x22c55e, 0.017, 0.0);
  cutaway.addFlowPulseOnEdge(0, 0x22c55e, 0.017, 0.5);

  cutaway.updateShaft = (lt, dur) => {
    const u = clamp(lt / Math.max(0.2, dur), 0, 1);
    cutaway.setReveal(smooth(clamp(u * 2.5, 0, 1)));
    cutaway.updateFlow(lt, 1.3);
    const travel = smooth(u);
    const carY = lerp(0.54, 1.88, travel);
    const cwY = lerp(1.92, 0.58, travel); // Exact opposite displacement!
    carGroup.position.y = carY;
    cwGroup.position.y = cwY;
    topSheave.rotation.z = -travel * Math.PI * 2.6;

    // Stretch ropes cleanly between car/cw tops and topSheave (y=2.38)
    const carTop = carY + 0.42;
    const carLen = Math.max(0.1, 2.38 - carTop);
    ropeCar.scale.set(1, carLen, 1);
    ropeCar.position.set(-0.22, carTop + carLen * 0.5, -0.02);

    const cwTop = cwY + 0.36;
    const cwLen = Math.max(0.1, 2.38 - cwTop);
    ropeCw.scale.set(1, cwLen, 1);
    ropeCw.position.set(0.42, cwTop + cwLen * 0.5, -0.02);

    for (const s of sensors) {
      const dist = Math.abs(carY - s.y);
      const active = dist < 0.24 ? (1.0 - dist / 0.24) : 0.0;
      s.mat.emissiveIntensity = 0.15 + active * 2.1;
      s.mat.emissive.setHex(active > 0.3 ? 0x22c55e : 0x0ea5e9);
    }
  };
  return shadow(cutaway.root), cutaway;
}

/**
 * 5. Architectural Landing Doors Portal: visible sill alignment & bi-parting doors opening ONLY after leveling.
 */
export function makeLandingDoorsRig() {
  const M = materials();
  const g = new THREE.Group();

  const wallMat = new THREE.MeshStandardMaterial({ color: 0xe2e8f0, roughness: 0.78 });
  const frameMat = new THREE.MeshPhysicalMaterial({ color: 0x475569, metalness: 0.82, roughness: 0.28 });
  const doorMat = new THREE.MeshPhysicalMaterial({ color: 0xcbd5e1, metalness: 0.88, roughness: 0.24, clearcoat: 0.25 });

  // Portal jambs & header
  const leftWall = new THREE.Mesh(new THREE.BoxGeometry(0.85, 2.5, 0.22), wallMat);
  leftWall.position.set(-0.98, 1.25, 0.0);
  const rightWall = new THREE.Mesh(new THREE.BoxGeometry(0.85, 2.5, 0.22), wallMat);
  rightWall.position.set(0.98, 1.25, 0.0);
  const header = new THREE.Mesh(new THREE.BoxGeometry(1.14, 0.46, 0.24), frameMat);
  header.position.set(0, 2.27, 0.0);
  const sill = new THREE.Mesh(new THREE.BoxGeometry(1.22, 0.04, 0.28), M.steelDark);
  sill.position.set(0, 0.02, 0.04);
  g.add(leftWall, rightWall, header, sill);

  // Interior warm elevator cabin visible behind bi-parting doors
  const carBack = new THREE.Mesh(
    new THREE.BoxGeometry(1.06, 2.02, 0.85),
    new THREE.MeshStandardMaterial({ color: 0xfef3c7, emissive: 0xfde68a, emissiveIntensity: 0.22, roughness: 0.5, side: THREE.BackSide })
  );
  carBack.position.set(0, 1.03, -0.52);
  g.add(carBack);

  // Leveling lock indicator LED bar on header
  const levelLedMat = new THREE.MeshStandardMaterial({ color: 0x38bdf8, emissive: 0xf59e0b, emissiveIntensity: 0.4 });
  const levelLed = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.05, 0.04), levelLedMat);
  levelLed.position.set(0, 2.15, 0.13);
  g.add(levelLed);

  // Bi-parting sliding doors
  const doorL = new THREE.Mesh(new THREE.BoxGeometry(0.55, 2.00, 0.045), doorMat);
  doorL.position.set(-0.28, 1.02, 0.08);
  const doorR = new THREE.Mesh(new THREE.BoxGeometry(0.55, 2.00, 0.045), doorMat);
  doorR.position.set(0.28, 1.02, 0.08);
  g.add(doorL, doorR);

  // Floor landing call button box on right jamb (consistent callback anchor)
  const panel = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.26, 0.03), M.steelBright);
  panel.position.set(0.70, 1.16, 0.12);
  const btnMat = new THREE.MeshStandardMaterial({ color: 0xfbbf24, emissive: 0xf59e0b, emissiveIntensity: 1.4 });
  const btn = new THREE.Mesh(new THREE.CylinderGeometry(0.024, 0.024, 0.02, 24), btnMat);
  btn.rotation.x = Math.PI / 2;
  btn.position.set(0.70, 1.15, 0.14);
  g.add(panel, btn);

  g.updatePortal = (lt, dur, { startOpen = false } = {}) => {
    const u = clamp(lt / Math.max(0.2, dur), 0, 1);
    // Car levels smoothly onto floor sill during u=0..0.38; doors unlock & slide open ONLY for u >= 0.42!
    const levelU = startOpen ? 1.0 : smooth(clamp(u / 0.36, 0, 1));
    carBack.position.y = lerp(0.76, 1.03, levelU);
    const leveled = levelU >= 0.96;
    levelLedMat.emissive.setHex(leveled ? 0x22c55e : 0xf59e0b);
    levelLedMat.emissiveIntensity = leveled ? 1.7 : 0.6;

    const doorOpen = startOpen ? 1.0 : (leveled ? smooth(clamp((u - 0.42) / 0.46, 0, 1)) : 0.0);
    doorL.position.x = lerp(-0.28, -0.76, doorOpen);
    doorR.position.x = lerp(0.28, 0.76, doorOpen);
    btnMat.emissiveIntensity = leveled && doorOpen > 0.5 ? 0.35 : 1.5;
  };
  return shadow(g);
}

/**
 * 6. Truthful Labeled Stylized Schematic Mechanism Stage (used ONLY when exact 3D domain archetype is unsupported).
 */
export function makeSchematicMechanismStage(labelText = 'SCHEMATIC') {
  const M = materials();
  const g = new THREE.Group();
  const plinth = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.62, 0.22, 32), M.steelDark);
  plinth.position.y = 0.11;
  g.add(plinth);

  const badge = new THREE.Mesh(
    new THREE.PlaneGeometry(0.78, 0.24),
    new THREE.MeshStandardMaterial({ map: makeDisplayTexture('STYLIZED MODEL', labelText.slice(0, 12).toUpperCase(), '#38bdf8'), roughness: 0.4 })
  );
  badge.position.set(0, 0.26, 0.56);
  g.add(badge);

  const wheels = [];
  for (let idx = 0; idx < 2; idx++) {
    const w = new THREE.Group();
    const rad = idx === 0 ? 0.26 : 0.16;
    const rim = new THREE.Mesh(new THREE.TorusGeometry(rad, 0.025, 10, 28), idx === 0 ? M.steelBright : M.copper);
    w.add(rim);
    for (let s = 0; s < 6; s++) {
      const sp = new THREE.Mesh(new THREE.BoxGeometry(0.02, rad * 1.9, 0.018), M.steel);
      sp.rotation.z = (s / 6) * Math.PI;
      w.add(sp);
    }
    w.position.set(idx === 0 ? -0.24 : 0.24, 1.05, 0);
    g.add(w);
    wheels.push(w);
  }
  const link = new THREE.Mesh(new THREE.BoxGeometry(0.52, 0.04, 0.04), M.copper);
  link.position.set(0, 1.05, 0.04);
  g.add(link);

  g.wheels = wheels;
  g.link = link;
  return shadow(g);
}
"""
