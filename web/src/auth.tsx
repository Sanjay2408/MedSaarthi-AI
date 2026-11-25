import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, type Me, type Profile } from "./api";

type AuthState = {
  loading: boolean;
  user: Me["user"];
  profiles: Profile[];
  profile: Profile | null;
  setProfileId: (id: number) => void;
  refresh: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<Me>;
  signUp: (body: Parameters<typeof api.signup>[0]) => Promise<Me>;
  signOut: () => Promise<void>;
  updateProfile: (id: number, patch: Partial<Profile>) => Promise<void>;
  setMe: (me: Me) => void;
};

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me>({ user: null, profiles: [] });
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMe(await api.me());
    } catch {
      setMe({ user: null, profiles: [] });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const profile = useMemo(
    () => me.profiles.find((p) => p.id === activeId) ?? me.profiles.find((p) => p.is_default) ?? me.profiles[0] ?? null,
    [me.profiles, activeId],
  );

  const value: AuthState = {
    loading,
    user: me.user,
    profiles: me.profiles,
    profile,
    setProfileId: setActiveId,
    refresh,
    setMe,
    signIn: async (email, password) => {
      const next = await api.login(email, password);
      setMe(next);
      setActiveId(null);
      return next;
    },
    signUp: async (body) => {
      const next = await api.signup(body);
      setMe(next);
      setActiveId(null);
      return next;
    },
    signOut: async () => {
      await api.logout().catch(() => undefined);
      setMe({ user: null, profiles: [] });
      setActiveId(null);
    },
    updateProfile: async (id, patch) => {
      const updated = await api.patchProfile(id, patch);
      setMe((m) => ({ ...m, profiles: m.profiles.map((p) => (p.id === id ? updated : p)) }));
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth outside AuthProvider");
  return v;
}

/** What the app says, in the register that suits the person. Same facts, different voice. */
export function voice(age: Profile["age_band"] | undefined, key: "hello" | "careful" | "thinking" | "done", name = ""): { title: string; line: string } {
  const table = {
    child: {
      hello: { title: `Hi${name ? ` ${name}` : ""}! I'm Saarthi.`, line: "Show me the paper and we'll work it out together." },
      careful: { title: "Let's ask a grown-up to check this.", line: "I won't guess. A pharmacist or doctor will tell us what's right." },
      thinking: { title: "Reading…", line: "Give me a moment." },
      done: { title: "All done for today!", line: "Well done." },
    },
    adult: {
      hello: { title: "Hello, I'm Saarthi.", line: "Let's make sense of your prescription, in plain words and in your language. If anything is unclear I won't guess. We'll check it with your pharmacist." },
      careful: { title: "Let's double-check this.", line: "I won't guess, so it stays out of your plan until your pharmacist has checked it." },
      thinking: { title: "One moment…", line: "Reading it carefully." },
      done: { title: "That's everything for today.", line: "" },
    },
    senior: {
      hello: { title: `Hello${name ? ` ${name}` : ""}.`, line: "Please show me your prescription. I will read it slowly, and I will not guess." },
      careful: { title: "This needs your pharmacist.", line: "I am not sure about one part, so I have left it out. Please show it to your pharmacist." },
      thinking: { title: "Reading slowly…", line: "This takes a few seconds." },
      done: { title: "You have taken everything for today.", line: "" },
    },
  } as const;
  return table[age ?? "adult"][key];
}
