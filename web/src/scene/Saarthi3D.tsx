import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import type * as THREE from "three";
import type { Mood } from "../Saarthi";
import { useTokens } from "./theme";

// Saarthi in 3D: a capsule, two tones, a face that follows the situation.
// Calm by design: it sways, blinks and waves. It never bounces on a warning.
type Props = { mood: Mood; size: number; speed: number; still: boolean };

function Body({ mood, speed, still }: Omit<Props, "size">) {
  const t = useTokens(
    { top: "--capsule-top", low: "--capsule-low", line: "--capsule-line", spark: "--spark" },
    { top: "#12907f", low: "#ffffff", line: "#0a4a41", spark: "#e5a400" },
  );
  const root = useRef<THREE.Group>(null!);
  const arm = useRef<THREE.Group>(null!);
  const eyes = useRef<THREE.Group>(null!);
  const spark = useRef<THREE.Group>(null!);

  useFrame(({ clock }) => {
    if (still) return;
    const s = clock.elapsedTime * speed;
    root.current.position.y = Math.sin(s * 1.8) * 0.04 + (mood === "happy" ? Math.abs(Math.sin(s * 4.5)) * 0.2 : 0);
    root.current.rotation.z = Math.sin(s * 1.1) * 0.05 + (mood === "thinking" ? -0.12 : 0);
    root.current.rotation.y = Math.sin(s * 0.7) * 0.2;
    const open = s % 4.3 > 4.18 ? 0.1 : 1;
    eyes.current.scale.y += (open - eyes.current.scale.y) * 0.5;
    arm.current.rotation.z = mood === "hello" ? -0.55 + Math.sin(s * 7) * 0.45 : -0.1;
    if (spark.current) spark.current.rotation.y = s * 1.5;
  });

  const matTop = <meshStandardMaterial color={t.top} roughness={0.35} metalness={0.05} />;
  const matLow = <meshStandardMaterial color={t.low} roughness={0.4} />;
  const ink = <meshBasicMaterial color={t.line} />;
  const happy = mood === "happy";

  return (
    <group ref={root} position={[0, -0.05, 0]}>
      <group position={[0, -0.05, 0]}>
        <mesh position={[0, 0.45, 0]}><sphereGeometry args={[0.55, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2]} />{matTop}</mesh>
        <mesh position={[0, 0.225, 0]}><cylinderGeometry args={[0.55, 0.55, 0.45, 32, 1, true]} />{matTop}</mesh>
        <mesh position={[0, -0.225, 0]}><cylinderGeometry args={[0.55, 0.55, 0.45, 32, 1, true]} />{matLow}</mesh>
        <mesh position={[0, -0.45, 0]}><sphereGeometry args={[0.55, 32, 16, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2]} />{matLow}</mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[0.553, 0.022, 8, 64]} />{ink}</mesh>
      </group>

      <group position={[0, 0.02, 0.5]}>
        <group ref={eyes}>
          {happy ? (
            <>
              <mesh position={[-0.2, 0.13, 0.02]}><torusGeometry args={[0.07, 0.018, 8, 16, Math.PI]} />{ink}</mesh>
              <mesh position={[0.2, 0.13, 0.02]}><torusGeometry args={[0.07, 0.018, 8, 16, Math.PI]} />{ink}</mesh>
            </>
          ) : (
            <>
              <mesh position={[-0.2, 0.13, 0.02]} scale={[1, mood === "careful" ? 0.85 : 1, 0.6]}><sphereGeometry args={[0.07, 16, 12]} />{ink}</mesh>
              <mesh position={[0.2, 0.13, 0.02]} scale={[1, mood === "careful" ? 0.85 : 1, 0.6]}><sphereGeometry args={[0.07, 16, 12]} />{ink}</mesh>
            </>
          )}
        </group>
        {mood === "careful" && (
          <>
            <mesh position={[-0.2, 0.27, 0.02]} rotation={[0, 0, -0.35]}><boxGeometry args={[0.14, 0.022, 0.02]} />{ink}</mesh>
            <mesh position={[0.2, 0.27, 0.02]} rotation={[0, 0, 0.35]}><boxGeometry args={[0.14, 0.022, 0.02]} />{ink}</mesh>
          </>
        )}
        {(mood === "hello" || happy) && (
          <mesh position={[0, -0.06, 0.02]} rotation={[0, 0, Math.PI]}><torusGeometry args={[happy ? 0.15 : 0.11, 0.02, 8, 24, Math.PI]} />{ink}</mesh>
        )}
        {mood === "thinking" && <mesh position={[0.04, -0.12, 0.02]}><sphereGeometry args={[0.035, 12, 8]} />{ink}</mesh>}
        {mood === "careful" && <mesh position={[0, -0.12, 0.02]}><boxGeometry args={[0.16, 0.022, 0.02]} />{ink}</mesh>}
      </group>

      <group ref={arm} position={[0.52, 0.05, 0]}>
        <mesh position={[0.12, 0.2, 0]} rotation={[0, 0, -0.5]}><capsuleGeometry args={[0.06, 0.25, 4, 12]} />{matLow}</mesh>
      </group>

      {happy && (
        <group ref={spark}>
          {[[-0.85, 0.7], [0.85, 0.9]].map(([x, y], i) => (
            <mesh key={i} position={[x, y, 0]} scale={i ? 0.8 : 1}><octahedronGeometry args={[0.09]} /><meshBasicMaterial color={t.spark} /></mesh>
          ))}
        </group>
      )}
    </group>
  );
}

export default function Saarthi3D({ mood, size, speed, still }: Props) {
  return (
    <div style={{ width: size, height: size }} aria-hidden="true">
      <Canvas flat dpr={[1, 1.75]} frameloop={still ? "demand" : "always"} camera={{ fov: 30, position: [0, 0.25, 4.4] }}
              gl={{ antialias: true, alpha: true, powerPreference: "low-power" }}>
        <ambientLight intensity={1.25} />
        <directionalLight position={[2, 3, 4]} intensity={2.1} />
        <Body mood={mood} speed={speed} still={still} />
      </Canvas>
    </div>
  );
}
