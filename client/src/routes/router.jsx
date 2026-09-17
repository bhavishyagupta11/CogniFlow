import { createBrowserRouter, Navigate, useRouteError } from "react-router-dom";
import { Layout } from "@/components/layout/Layout";
import { ChatPage } from "@/pages/ChatPage";
import { DocumentsPage } from "@/pages/DocumentsPage";
import { EvaluationPage } from "@/pages/EvaluationPage";
import { AuthPage } from "@/pages/AuthPage";
import { ArchitecturePage } from "@/pages/ArchitecturePage";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

function RouteErrorBoundary() {
    const error = useRouteError();
    return (<div className="flex h-screen w-screen items-center justify-center p-6 bg-[var(--bg-page)] text-[var(--text-primary)]">
      <div className="max-w-md w-full border border-[var(--panel-border)] bg-[var(--panel-bg)] p-6 rounded-[4px] shadow-sm space-y-4 font-mono">
        <div className="flex items-center gap-2 text-rose-600 font-bold uppercase tracking-wider text-xs">
          <AlertCircle className="h-4 w-4"/>
          <span>Application State Recovery</span>
        </div>
        <p className="text-xs text-[var(--text-secondary)] font-sans">
          An interface event occurred. You can safely return to the active terminal.
        </p>
        <div className="p-2 bg-[var(--panel-inner)] border border-[var(--panel-border)] rounded-[2px] text-[10px] text-[var(--text-muted)] truncate">
          {error?.message || String(error)}
        </div>
        <Button onClick={() => (window.location.href = "/")} className="w-full bg-[var(--accent-amber)] text-black hover:bg-[var(--accent-amber-hover)] text-xs font-mono font-bold uppercase rounded-[2px] h-8">
          <RefreshCw className="mr-1.5 h-3.5 w-3.5"/>
          Reload CogniFlow Terminal
        </Button>
      </div>
    </div>);
}

export const router = createBrowserRouter([
    {
        path: "/",
        element: <Layout />,
        errorElement: <RouteErrorBoundary />,
        children: [
            {
                index: true,
                element: <ChatPage />,
            },
            {
                path: "documents",
                element: <DocumentsPage />,
            },
            {
                path: "eval",
                element: <EvaluationPage />,
            },
            {
                path: "evaluation",
                element: <EvaluationPage />,
            },
            {
                path: "architecture",
                element: <ArchitecturePage />,
            },
            {
                path: "auth",
                element: <AuthPage />,
            },
            {
                path: "settings",
                element: <AuthPage />,
            },
            {
                path: "*",
                element: <Navigate to="/" replace/>,
            },
        ],
    },
]);
