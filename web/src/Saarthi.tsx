import type { ReactNode } from "react";

// Saarthi means guide or charioteer: the companion who rides beside you. Its moods follow the
// patient's situation. It is cheerful when things go well and quietly attentive when something
// needs checking. It never jokes about a dose or a warning.
export type Mood = "hello" | "thinking" | "careful" | "happy";

export function Saarthi({ mood = "hello", size = 72 }: { mood?: Mood; size?: number }) {
  return (
    <svg className={`saarthi mood-${mood}`} width={size} height={size} viewBox="0 0 80 80" aria-hidden="true">
      <g className="saarthi-body">
        <rect x="20" y="8" width="40" height="64" rx="20" className="capsule-low" />
        <path d="M20 40V28a20 20 0 0 1 40 0v12z" className="capsule-top" />
        <path d="M28 20a12 12 0 0 1 8-6" className="capsule-shine" />
        {mood === "happy" ? (
          <>
            <path d="M29 46q4-5 8 0" className="face-line" />
            <path d="M43 46q4-5 8 0" className="face-line" />
          </>
        ) : (
          <>
            <circle className="eye" cx={mood === "thinking" ? 34 : 33} cy={mood === "thinking" ? 45 : 47} r="3" />
            <circle className="eye" cx={mood === "thinking" ? 48 : 47} cy={mood === "thinking" ? 45 : 47} r="3" />
          </>
        )}
        {mood === "hello" && <path d="M33 54q7 7 14 0" className="face-line" />}
        {mood === "happy" && <path d="M31 53q9 11 18 0" className="face-line" />}
        {mood === "thinking" && <path d="M36 57h8" className="face-line" />}
        {mood === "careful" && (
          <>
            <path d="M34 56q6 3 12 0" className="face-line" />
            <path d="M29 42l7-2M51 42l-7-2" className="face-line thin" />
          </>
        )}
      </g>
      {mood === "hello" && <path className="saarthi-wave" d="M62 38q8-3 10-11" />}
      {mood === "thinking" && (
        <g className="saarthi-dots">
          <circle cx="66" cy="20" r="2.4" />
          <circle cx="72" cy="13" r="3" />
          <circle cx="76" cy="5" r="3.6" />
        </g>
      )}
      {mood === "happy" && (
        <g className="saarthi-sparks">
          <path d="M9 24l1.8 4.2 4.2 1.8-4.2 1.8L9 36l-1.8-4.2L3 30l4.2-1.8z" />
          <path d="M70 12l1.4 3.1 3.1 1.4-3.1 1.4L70 21l-1.4-3.1-3.1-1.4 3.1-1.4z" />
        </g>
      )}
    </svg>
  );
}

export function Says({ mood, children, live }: { mood: Mood; children: ReactNode; live?: boolean }) {
  return (
    <div className={`says says-${mood}`} role={live ? "status" : undefined}>
      <Saarthi mood={mood} />
      <div className="bubble">{children}</div>
    </div>
  );
}
