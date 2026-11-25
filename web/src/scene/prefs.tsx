import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import type { AgeBand } from "../api";

// One place that decides how much animation a person gets.
//   mode   "3d" only when WebGL works, the device is not weak, and neither the person nor their
//          system asked for reduced motion. Otherwise "flat": the same information as tiles.
//   speed  child 1.15, adult 1, senior 0.6 (slower and calmer)
//   bounce how springy things are: lively for a child, none for a senior
export type ScenePrefs = { mode: "3d" | "flat"; speed: number; bounce: number; age: AgeBand; still: boolean };
export type DevicePref = "auto" | "on" | "off";
const KEY = "ms-scene";

export function readDevicePref(): DevicePref {
  try {
    const v = localStorage.getItem(KEY);
    return v === "on" || v === "off" ? v : "auto";
  } catch {
    return "auto";
  }
}

export function writeDevicePref(v: DevicePref) {
  try {
    localStorage.setItem(KEY, v);
  } catch {
    /* private window: applies for this visit only */
  }
  window.dispatchEvent(new Event("ms-scene-change"));
}

let webgl: boolean | undefined;
function webglOk(): boolean {
  if (webgl === undefined) {
    try {
      const c = document.createElement("canvas");
      webgl = Boolean(c.getContext("webgl2") || c.getContext("webgl"));
    } catch {
      webgl = false;
    }
  }
  return webgl;
}

function weakDevice(): boolean {
  const nav = navigator as Navigator & { deviceMemory?: number };
  return (nav.hardwareConcurrency ?? 4) <= 2 || (nav.deviceMemory ?? 4) <= 2;
}

export function decide(pref: DevicePref, reduceMotion: boolean, systemReduced: boolean, age: AgeBand): ScenePrefs {
  const calm = reduceMotion || systemReduced;
  const wants = pref === "on" ? true : pref === "off" ? false : !weakDevice();
  const mode = wants && webglOk() && !(calm && pref !== "on") ? "3d" : "flat";
  return { mode, age, speed: age === "senior" ? 0.6 : age === "child" ? 1.15 : 1, bounce: age === "child" ? 0.45 : age === "senior" ? 1 : 0.7, still: calm };
}

const Ctx = createContext<ScenePrefs>({ mode: "flat", speed: 1, bounce: 0.7, age: "adult", still: true });

export function ScenePrefsProvider({ age, reduceMotion, children }: { age: AgeBand; reduceMotion: boolean; children: ReactNode }) {
  const [pref, setPref] = useState<DevicePref>(readDevicePref);
  const [system, setSystem] = useState(() => window.matchMedia("(prefers-reduced-motion: reduce)").matches);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const onMq = () => setSystem(mq.matches);
    const onPref = () => setPref(readDevicePref());
    mq.addEventListener("change", onMq);
    window.addEventListener("ms-scene-change", onPref);
    return () => {
      mq.removeEventListener("change", onMq);
      window.removeEventListener("ms-scene-change", onPref);
    };
  }, []);

  const value = useMemo(() => decide(pref, reduceMotion, system, age), [pref, reduceMotion, system, age]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useScenePrefs = () => useContext(Ctx);
