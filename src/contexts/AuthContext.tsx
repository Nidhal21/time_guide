import { createContext, useContext, useEffect, useState, ReactNode } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000/api";
const STORAGE_KEY = "auth_token";

export interface AuthUser {
  id: string;
  email: string;
  full_name?: string | null;
  role: "admin" | "user";
  created_at?: string | null;
}

interface Session {
  access_token: string;
  token_type: string;
  expires_at: string;
}

interface AuthContextType {
  user: AuthUser | null;
  session: Session | null;
  isAdmin: boolean;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: Error | null; user: AuthUser | null }>;
  signUp: (
    email: string,
    password: string,
    fullName?: string,
  ) => Promise<{ error: Error | null; user: AuthUser | null }>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const readStoredToken = () => localStorage.getItem(STORAGE_KEY);

const persistSession = (session: Session | null) => {
  if (session?.access_token) {
    localStorage.setItem(STORAGE_KEY, session.access_token);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
};

const apiFetch = async (path: string, init: RequestInit = {}, token?: string | null) => {
  const headers = new Headers(init.headers ?? {});
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.detail || "Erreur d'authentification.");
  }
  return body;
};

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const applyAuthState = (nextUser: AuthUser | null, nextSession: Session | null) => {
    setUser(nextUser);
    setSession(nextSession);
    setIsAdmin(nextUser?.role === "admin");
    persistSession(nextSession);
  };

  useEffect(() => {
    const bootstrap = async () => {
      const token = readStoredToken();
      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const data = await apiFetch("/auth/me", { method: "GET" }, token);
        applyAuthState(data.user, {
          access_token: token,
          token_type: "bearer",
          expires_at: "",
        });
      } catch {
        applyAuthState(null, null);
      } finally {
        setIsLoading(false);
      }
    };

    bootstrap();
  }, []);

  const signIn = async (email: string, password: string) => {
    try {
      const data = await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      applyAuthState(data.user, data.session);
      return { error: null, user: data.user as AuthUser };
    } catch (error) {
      return { error: error instanceof Error ? error : new Error("Erreur inconnue."), user: null };
    }
  };

  const signUp = async (email: string, password: string, fullName?: string) => {
    try {
      const data = await apiFetch("/auth/signup", {
        method: "POST",
        body: JSON.stringify({ email, password, full_name: fullName }),
      });
      applyAuthState(data.user, data.session);
      return { error: null, user: data.user as AuthUser };
    } catch (error) {
      return { error: error instanceof Error ? error : new Error("Erreur inconnue."), user: null };
    }
  };

  const signOut = async () => {
    const token = readStoredToken();
    try {
      if (token) {
        await apiFetch("/auth/logout", { method: "POST" }, token);
      }
    } catch {
      // Keep logout resilient even if backend session is already gone.
    } finally {
      applyAuthState(null, null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, session, isAdmin, isLoading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
};
