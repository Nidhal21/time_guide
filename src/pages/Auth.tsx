import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, GraduationCap, Loader2, Lock, Mail, UserRound } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { useAuth } from "@/contexts/AuthContext";


type AuthMode = "signin" | "signup";


const Auth = () => {
  const [mode, setMode] = useState<AuthMode>("signin");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { user, signIn, signUp } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) return;
    navigate(user.role === "admin" ? "/admin" : "/chat", { replace: true });
  }, [navigate, user]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const result =
      mode === "signin"
        ? await signIn(email, password)
        : await signUp(email, password, fullName);

    if (result.error) {
      setError(result.error.message);
      setLoading(false);
      return;
    }

    navigate(result.user?.role === "admin" ? "/admin" : "/chat");
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-[linear-gradient(180deg,#f8fafc_0%,#eef4fb_55%,#f8fafc_100%)] px-4 py-10">
      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full max-w-md"
      >
        <div className="mb-8 text-center">
          <Link to="/chat" className="inline-block">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl gradient-hero shadow-glow-primary">
              <GraduationCap className="h-7 w-7 text-primary-foreground" />
            </div>
          </Link>
          <h1 className="font-display text-2xl font-bold text-foreground">Espace compte</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Connexion pour les utilisateurs et l&apos;admin, inscription simple pour les etudiants.
          </p>
        </div>

        <div className="rounded-[1.6rem] border border-slate-200 bg-white p-2 shadow-[0_18px_50px_-28px_rgba(15,23,42,0.28)]">
          <div className="grid grid-cols-2 gap-2 rounded-[1.1rem] bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => {
                setMode("signin");
                setError("");
              }}
              className={`rounded-[0.9rem] px-4 py-2.5 text-sm font-medium transition ${
                mode === "signin" ? "bg-white text-slate-950 shadow-sm" : "text-slate-600"
              }`}
            >
              Connexion
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("signup");
                setError("");
              }}
              className={`rounded-[0.9rem] px-4 py-2.5 text-sm font-medium transition ${
                mode === "signup" ? "bg-white text-slate-950 shadow-sm" : "text-slate-600"
              }`}
            >
              Inscription
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4 px-4 pb-4 pt-5">
            {mode === "signup" && (
              <div className="space-y-1.5">
                <label className="text-sm font-medium text-foreground">Nom complet</label>
                <div className="relative">
                  <UserRound className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Votre nom"
                    required
                    className="w-full rounded-xl border border-input bg-background py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Email</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="vous@enetcom.tn"
                  required
                  className="w-full rounded-xl border border-input bg-background py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-foreground">Mot de passe</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="w-full rounded-xl border border-input bg-background py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
            </div>

            {error && (
              <p className="rounded-xl bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl gradient-primary py-2.5 text-sm font-medium text-primary-foreground shadow-soft transition-shadow hover:shadow-glow-primary disabled:opacity-50"
            >
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  {mode === "signin" ? "Se connecter" : "Creer mon compte"}
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center">
          <Link to="/chat" className="text-sm text-muted-foreground hover:text-foreground">
            Retour au chatbot
          </Link>
        </p>
      </motion.div>
    </div>
  );
};


export default Auth;
