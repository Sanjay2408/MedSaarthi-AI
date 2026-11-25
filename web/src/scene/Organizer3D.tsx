import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { spring, useTokens } from "./theme";

// The patient's day as a pill organizer: four lids, Morning to Night. Tap a lid to open it. A
// dose that has been ticked leaves its compartment. A small sun or moon floats over "now".
// It repeats what the tiles below already say in text; nothing here is the only place to find a
// dose, and every control also exists as a real button in the page.
export type OrganizerSlot = {
  period: "Morning" | "Afternoon" | "Evening" | "Night";
  doses: { key: string; hue: number; done: boolean }[];
};
type Props = {
  slots: OrganizerSlot[];
  selected: string | null;
  now: OrganizerSlot["period"];
  onSelect: (period: string) => void;
  speed: number;
  bounce: number;
  still: boolean;
  height: number;
};

const W = 1.0;
const GAP = 0.09;
const x = (i: number) => (i - 1.5) * (W + GAP);
const PILLS = ["#e5484d", "#2f7de1", "#f2a900", "#1f9d68", "#e8703a", "#12907f"];

function Lid({ i, color, open, glow, onSelect, bounce, still, period }: {
  i: number; color: string; open: boolean; glow: boolean; onSelect: () => void; bounce: number; still: boolean; period: string;
}) {
  const hinge = useRef<THREE.Group>(null!);
  const vel = useRef(0);
  const invalidate = useThree((s) => s.invalidate);
  const target = open ? -1.85 : 0;

  useEffect(() => {
    if (still && hinge.current) {
      hinge.current.rotation.x = target; // no animation: jump to the end pose
      invalidate();
    }
  }, [still, target, invalidate]);

  useFrame((_, dt) => {
    if (still) return;
    const [v, s] = spring(hinge.current.rotation.x, vel.current, target, bounce, dt, 55);
    hinge.current.rotation.x = v;
    vel.current = s;
  });

  return (
    <group ref={hinge} position={[x(i), 0.2, -0.66]}>
      <mesh position={[0, 0.045, 0.66]} onClick={(e) => { e.stopPropagation(); onSelect(); }}
            onPointerOver={() => { document.body.style.cursor = "pointer"; }} onPointerOut={() => { document.body.style.cursor = ""; }}>
        <boxGeometry args={[W - 0.04, 0.09, 1.32]} />
        <meshStandardMaterial color={color} roughness={0.45} emissive={glow ? color : "#000000"} emissiveIntensity={glow ? 0.28 : 0} />
      </mesh>
      <Icon period={period} color="#ffffff" />
    </group>
  );
}

function Icon({ period, color }: { period: string; color: string }) {
  const moon = useMemo(() => {
    const s = new THREE.Shape();
    s.absarc(0, 0, 0.2, Math.PI * 0.2, Math.PI * 1.8, false);
    s.absarc(0.1, 0.02, 0.16, Math.PI * 1.7, Math.PI * 0.3, true);
    return new THREE.ShapeGeometry(s, 24);
  }, []);
  const m = <meshBasicMaterial color={color} />;
  if (period === "Night") return <mesh geometry={moon} position={[0, 0.095, 0.66]} rotation={[-Math.PI / 2, 0, 0]}>{m}</mesh>;
  if (period === "Evening") return <mesh position={[0, 0.095, 0.66]}><sphereGeometry args={[0.17, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2]} />{m}</mesh>;
  return <mesh position={[0, 0.1, 0.66]} scale={[1, 0.25, 1]}><sphereGeometry args={[period === "Morning" ? 0.14 : 0.18, 20, 12]} />{m}</mesh>;
}

function Pill({ pos, color, spin, still }: { pos: [number, number, number]; color: string; spin: boolean; still: boolean }) {
  const ref = useRef<THREE.Mesh>(null!);
  useFrame(({ clock }) => {
    if (still) return;
    ref.current.rotation.y = spin ? Math.sin(clock.elapsedTime * 5 + pos[0] * 7) * 0.25 : 0;
  });
  return (
    <mesh ref={ref} position={pos} rotation={[0, 0, Math.PI / 2]}>
      <capsuleGeometry args={[0.08, 0.18, 6, 14]} />
      <meshStandardMaterial color={color} roughness={0.3} />
    </mesh>
  );
}

function Marker({ now, still, colors }: { now: Props["now"]; still: boolean; colors: Record<string, string> }) {
  const ref = useRef<THREE.Group>(null!);
  const idx = ["Morning", "Afternoon", "Evening", "Night"].indexOf(now);
  const moon = useMemo(() => {
    const s = new THREE.Shape();
    s.absarc(0, 0, 0.17, Math.PI * 0.2, Math.PI * 1.8, false);
    s.absarc(0.09, 0.02, 0.14, Math.PI * 1.7, Math.PI * 0.3, true);
    return new THREE.ShapeGeometry(s, 24);
  }, []);
  useFrame(({ clock }, dt) => {
    const g = ref.current;
    g.position.x += (x(idx) - g.position.x) * (still ? 1 : Math.min(1, dt * 4));
    g.position.y = 1.15 + (still ? 0 : Math.sin(clock.elapsedTime * 1.6) * 0.06);
  });
  return (
    <group ref={ref} position={[x(idx), 1.15, 0.2]}>
      {now === "Night" ? (
        <mesh geometry={moon}><meshBasicMaterial color={colors.Night} side={THREE.DoubleSide} /></mesh>
      ) : (
        <mesh><sphereGeometry args={[now === "Evening" ? 0.14 : 0.17, 20, 14]} /><meshBasicMaterial color={colors[now]} /></mesh>
      )}
    </group>
  );
}

function Rig() {
  const { camera, size } = useThree();
  useEffect(() => {
    const cam = camera as THREE.PerspectiveCamera;
    const aspect = size.width / size.height;
    const dist = Math.max(4.7, 2.75 / (Math.tan((cam.fov * Math.PI) / 360) * aspect));
    cam.position.set(0, dist * 0.42, dist * 0.92);
    cam.lookAt(0, 0.45, 0);
    cam.updateProjectionMatrix();
  }, [camera, size.width, size.height]);
  return null;
}

function Scene({ slots, selected, now, onSelect, speed, bounce, still }: Omit<Props, "height">) {
  const t = useTokens(
    { m: "--morning-art", a: "--afternoon-art", e: "--evening-art", n: "--night-art", tray: "--raised", well: "--border" },
    { m: "#eeaa12", a: "#2f8fdc", e: "#e8703a", n: "#ffe08a", tray: "#e8f1ee", well: "#dfe8e5" },
  );
  const contrast = typeof document !== "undefined" && document.documentElement.hasAttribute("data-contrast");
  const lid = [t.m, t.a, t.e, contrast ? "#ffffff" : "#1d2f52"];
  const art = { Morning: t.m, Afternoon: t.a, Evening: t.e, Night: contrast ? "#ffd400" : t.n };
  const tray = useMemo(() => new RoundedBoxGeometry(4.7, 0.34, 1.72, 4, 0.09), []);
  const group = useRef<THREE.Group>(null!);

  useFrame(({ pointer }) => {
    if (still) return;
    group.current.rotation.y += (pointer.x * 0.12 * speed - group.current.rotation.y) * 0.06;
    group.current.rotation.x += (-pointer.y * 0.05 * speed - group.current.rotation.x) * 0.06;
  });

  return (
    <group ref={group}>
      <mesh geometry={tray}>
        <meshStandardMaterial color={contrast ? "#1f1f1f" : t.tray} roughness={0.7} />
      </mesh>
      {slots.map((s, i) => (
        <group key={s.period}>
          <mesh position={[x(i), 0.14, 0]}>
            <boxGeometry args={[W - 0.06, 0.08, 1.36]} />
            <meshStandardMaterial color={contrast ? "#000000" : t.well} roughness={0.9} />
          </mesh>
          {s.doses.map((d, j) => (!d.done && (
            <Pill key={d.key} pos={[x(i) + (j % 2 ? 0.2 : -0.2), 0.27, -0.35 + Math.floor(j / 2) * 0.32]}
                  color={contrast ? (d.hue % 2 ? "#ffd400" : "#ffffff") : PILLS[d.hue % PILLS.length]}
                  spin={selected === s.period} still={still} />
          )))}
          <Lid i={i} period={s.period} color={lid[i]} open={selected === s.period} glow={now === s.period && s.doses.some((d) => !d.done)}
               onSelect={() => onSelect(s.period)} bounce={bounce} still={still} />
        </group>
      ))}
      <Marker now={now} still={still} colors={art} />
    </group>
  );
}

export default function Organizer3D({ height, ...props }: Props) {
  return (
    <div style={{ width: "100%", height }} aria-hidden="true">
      <Canvas flat dpr={[1, 1.75]} frameloop={props.still ? "demand" : "always"} camera={{ fov: 28, position: [0, 3, 6.5] }}
              gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}>
        <ambientLight intensity={1.3} />
        <directionalLight position={[2.5, 5, 4]} intensity={2.2} />
        <Rig />
        <Scene {...props} />
      </Canvas>
    </div>
  );
}
