import { useEffect, useState } from "react";

/** Read CSS colour tokens so the 3D scene follows light, high contrast and every future theme. */
export function useTokens<T extends Record<string, string>>(names: T, fallbacks: Record<keyof T, string>): Record<keyof T, string> {
  const read = () => {
    const css = getComputedStyle(document.documentElement);
    return Object.fromEntries(Object.entries(names).map(([k, v]) => [k, css.getPropertyValue(v).trim() || fallbacks[k as keyof T]])) as Record<keyof T, string>;
  };
  const [tokens, setTokens] = useState(read);
  useEffect(() => {
    const watch = new MutationObserver(() => setTokens(read()));
    watch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-contrast", "data-large", "data-age"] });
    return () => watch.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return tokens;
}

/** A critically-damped-to-bouncy spring step. zeta 1 = no overshoot, below 1 = bounce. */
export function spring(value: number, velocity: number, target: number, zeta: number, dt: number, stiffness = 60): [number, number] {
  const d = Math.min(dt, 1 / 30);
  const damping = 2 * zeta * Math.sqrt(stiffness);
  const accel = -stiffness * (value - target) - damping * velocity;
  const v = velocity + accel * d;
  return [value + v * d, v];
}
