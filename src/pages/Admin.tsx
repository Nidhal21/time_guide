import { startTransition, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowRight,
  CalendarDays,
  CheckCircle2,
  CircleAlert,
  DoorOpen,
  FileSpreadsheet,
  GraduationCap,
  LogOut,
  RefreshCcw,
  ShieldCheck,
  UploadCloud,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/contexts/AuthContext";
import { getApiBaseUrl } from "@/lib/utils";

const API_URL = getApiBaseUrl();
const STORAGE_KEY = "auth_token";

type UploadSlotKey =
  | "student_s1"
  | "student_s2"
  | "rooms_s1"
  | "rooms_s2"
  | "teachers_s1"
  | "teachers_s2"
  | "calendar";

type LatestFileSummary = {
  filename: string;
  uploaded_at: string;
  size_label: string;
};

type CategorySummary = {
  key: UploadSlotKey;
  label: string;
  latest_file: LatestFileSummary | null;
};

type DashboardSummary = {
  calendar_warning?: string | null;
  categories: CategorySummary[];
};

type UploadResult = {
  category: UploadSlotKey;
  label: string;
  status: "success" | "error";
  filename?: string;
  message: string;
  parsed_session_count?: number | null;
};

const slotMeta: Record<
  UploadSlotKey,
  {
    title: string;
    subtitle: string;
    icon: typeof GraduationCap;
  }
> = {
  student_s1: {
    title: "Etudiants S1",
    subtitle: "Excel des classes du semestre 1",
    icon: GraduationCap,
  },
  student_s2: {
    title: "Etudiants S2",
    subtitle: "Excel des classes du semestre 2",
    icon: GraduationCap,
  },
  rooms_s1: {
    title: "Salles S1",
    subtitle: "Excel des salles du semestre 1",
    icon: DoorOpen,
  },
  rooms_s2: {
    title: "Salles S2",
    subtitle: "Excel des salles du semestre 2",
    icon: DoorOpen,
  },
  teachers_s1: {
    title: "Enseignants S1",
    subtitle: "Excel des enseignants du semestre 1",
    icon: Users,
  },
  teachers_s2: {
    title: "Enseignants S2",
    subtitle: "Excel des enseignants du semestre 2",
    icon: Users,
  },
  calendar: {
    title: "Calendrier universitaire",
    subtitle: "Vacances, examens et periodes",
    icon: CalendarDays,
  },
};

const formatDateTime = (value?: string | null) => {
  if (!value) return "Jamais";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
};

const Admin = () => {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<Partial<Record<UploadSlotKey, File>>>({});
  const [results, setResults] = useState<UploadResult[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async () => {
    setError(null);
    setIsLoading(true);
    try {
      const token = localStorage.getItem(STORAGE_KEY);
      const response = await fetch(`${API_URL}/admin/imports/status`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (!response.ok) {
        throw new Error("Impossible de charger la page admin.");
      }
      const data = (await response.json()) as DashboardSummary;
      startTransition(() => setSummary(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  const anySelected = useMemo(
    () => Object.values(selectedFiles).some((file) => Boolean(file)),
    [selectedFiles],
  );

  const handleFileChange = (key: UploadSlotKey, file: File | null) => {
    setSelectedFiles((prev) => {
      const next = { ...prev };
      if (file) {
        next[key] = file;
      } else {
        delete next[key];
      }
      return next;
    });
  };

  const handleUpload = async () => {
    if (!anySelected) {
      toast.error("Selectionnez au moins un fichier Excel.");
      return;
    }

    const payload = new FormData();
    Object.entries(selectedFiles).forEach(([key, file]) => {
      if (file) payload.append(key, file);
    });

    setIsUploading(true);
    setError(null);

    try {
      const token = localStorage.getItem(STORAGE_KEY);
      const response = await fetch(`${API_URL}/admin/imports/upload`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: payload,
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.detail || "Import impossible.");
      }

      const data = await response.json();
      const uploadResults = (data.results ?? []) as UploadResult[];
      const errorResults = uploadResults.filter((result) => result.status === "error");

      setResults(uploadResults);
      setSummary(data.summary ?? null);
      setSelectedFiles({});
      setRefreshTick((value) => value + 1);

      setError(errorResults.length > 0 ? errorResults[0].message : null);

      uploadResults.forEach((result) => {
        if (result.status === "error") {
          toast.error(result.label, {
            description: result.message,
          });
          return;
        }

        toast.success(result.label, {
          description: result.message,
        });
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Erreur inconnue.";
      setError(message);
      toast.error(message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleSignOut = async () => {
    await signOut();
    navigate("/auth", { replace: true });
  };

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-8 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-900 text-white">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <div>
                <h1 className="font-display text-2xl font-bold text-slate-900">Administration</h1>
                <p className="text-sm text-slate-600">
                  Import des fichiers Excel pour les emplois du temps.
                </p>
                <p className="mt-1 text-xs text-slate-400">{user?.email ?? "admin"}</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Link
                to="/chat"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Retour au chatbot
                <ArrowRight className="h-4 w-4" />
              </Link>
              <button
                onClick={fetchSummary}
                disabled={isLoading}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              >
                <RefreshCcw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
                Actualiser
              </button>
              <button
                onClick={handleSignOut}
                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                <LogOut className="h-4 w-4" />
                Deconnexion
              </button>
            </div>
          </div>
        </header>

        <section className="mb-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-display text-xl font-semibold text-slate-900">Charger les fichiers</h2>
          <p className="mt-2 text-sm text-slate-600">
            Choisissez les fichiers a mettre a jour, puis cliquez sur <span className="font-medium">Importer</span>.
          </p>
          <div className="mt-5">
            <button
              onClick={handleUpload}
              disabled={!anySelected || isUploading}
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <UploadCloud className="h-4 w-4" />
              {isUploading ? "Import en cours..." : "Importer"}
            </button>
          </div>
        </section>

        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {summary?.calendar_warning && (
          <div className="mb-6 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{summary.calendar_warning}</span>
          </div>
        )}

        <section className="grid gap-4 md:grid-cols-2">
          {(summary?.categories ?? []).map((category) => {
            const meta = slotMeta[category.key];
            const Icon = meta.icon;
            const chosenFile = selectedFiles[category.key];

            return (
              <motion.div
                key={category.key}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                <div className="flex items-start gap-3">
                  <div className="rounded-2xl bg-slate-100 p-3 text-slate-700">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-display text-lg font-semibold text-slate-900">{meta.title}</h3>
                    <p className="text-sm text-slate-500">{meta.subtitle}</p>
                  </div>
                </div>

                <div className="mt-4 rounded-2xl bg-slate-50 px-4 py-3">
                  <p className="text-xs uppercase tracking-wide text-slate-400">Dernier fichier</p>
                  <p className="mt-1 text-sm font-medium text-slate-900">
                    {category.latest_file?.filename ?? "Aucun fichier"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {category.latest_file
                      ? `${formatDateTime(category.latest_file.uploaded_at)} • ${category.latest_file.size_label}`
                      : "Aucun import pour le moment"}
                  </p>
                </div>

                <div className="mt-4 rounded-2xl border border-dashed border-slate-300 p-4">
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:opacity-90">
                    <FileSpreadsheet className="h-4 w-4" />
                    Choisir un fichier
                    <input
                      key={`${category.key}-${refreshTick}`}
                      type="file"
                      accept=".xlsx,.xls"
                      className="hidden"
                      onChange={(event) => handleFileChange(category.key, event.target.files?.[0] ?? null)}
                    />
                  </label>

                  <p className="mt-3 text-sm text-slate-600">
                    {chosenFile ? chosenFile.name : "Aucun fichier selectionne"}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </section>

        <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="font-display text-xl font-semibold text-slate-900">Resultat des imports</h2>
          <div className="mt-4 space-y-3">
            {results.length === 0 ? (
              <div className="rounded-2xl bg-slate-50 px-4 py-4 text-sm text-slate-500">
                Aucun import lance pour cette session.
              </div>
            ) : (
              results.map((result) => (
                <div
                  key={`${result.category}-${result.filename}`}
                  className={`flex items-start gap-3 rounded-2xl px-4 py-4 text-sm ${
                    result.status === "success"
                      ? "border border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border border-red-200 bg-red-50 text-red-800"
                  }`}
                >
                  {result.status === "success" ? (
                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
                  ) : (
                    <CircleAlert className="mt-0.5 h-5 w-5 shrink-0" />
                  )}
                  <div>
                    <p className="font-medium">{result.label}</p>
                    <p className="mt-1">{result.message}</p>
                    {typeof result.parsed_session_count === "number" && result.parsed_session_count > 0 && (
                      <p className="mt-1 text-xs opacity-80">
                        {result.parsed_session_count} seances parsees
                      </p>
                    )}
                    {result.filename && <p className="mt-1 text-xs opacity-80">{result.filename}</p>}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default Admin;
