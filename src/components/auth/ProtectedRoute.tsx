import { Navigate } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/contexts/AuthContext";


const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!user) return <Navigate to="/auth" replace />;

  return <>{children}</>;
};


export default ProtectedRoute;
