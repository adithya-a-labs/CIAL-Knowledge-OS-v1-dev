import { useEffect } from "react";
import { Switch, Route, Router as WouterRouter, useLocation } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AuthProvider, useAuth } from "@/auth/AuthContext";
import { consumePostAuthRedirect, setPostAuthRedirect } from "@/auth/storage";
import AppShell from "@/components/layout/AppShell";
import WelcomeTransition from "@/components/auth/WelcomeTransition";
import { CommandPaletteProvider, CommandPalette } from "@/components/common/CommandPalette";
import DashboardPage from "@/pages/DashboardPage";
import AIAssistantPage from "@/pages/AIAssistantPage";
import DocumentWorkspacePage from "@/pages/DocumentWorkspacePage";
import KnowledgeCenterPage from "@/pages/KnowledgeCenterPage";
import WorkspacePage from "@/pages/WorkspacePage";
import SummaryWorkspacePage from "@/pages/SummaryWorkspacePage";
import DocumentsPage from "@/pages/DocumentsPage";
import FAQsPage from "@/pages/FAQsPage";
import ExpertDirectoryPage from "@/pages/ExpertDirectoryPage";
import LearningHubPage from "@/pages/LearningHubPage";
import KnowledgeGraphPage from "@/pages/KnowledgeGraphPage";
import KnowledgeGapsPage from "@/pages/KnowledgeGapsPage";
import DepartmentsPage from "@/pages/DepartmentsPage";
import AnalyticsPage from "@/pages/AnalyticsPage";
import AdminSettingsPage from "@/pages/AdminSettingsPage";
import AdminSystemMonitorPage from "@/pages/AdminSystemMonitorPage";
import LoginPage from "@/pages/LoginPage";
import SignupPage from "@/pages/SignupPage";
import NotFound from "@/pages/not-found";

const queryClient = new QueryClient();

function AppBootScreen({
  message = "Loading secure workspace...",
  error,
  onRetry,
}: {
  message?: string;
  error?: string | null;
  onRetry?: () => void;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f5f8f3]">
      <div className="text-center">
        <img src="/favicon.svg" alt="CIAL" className="mx-auto h-12 w-12 animate-pulse" />
        <p className="mt-4 text-sm font-medium text-slate-600">{message}</p>
        {error ? (
          <p className="mx-auto mt-3 max-w-md text-sm text-red-700">{error}</p>
        ) : null}
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-5 rounded-lg border border-[#b8c9b1] bg-white px-4 py-2 text-sm font-semibold text-[#25611f] shadow-sm transition hover:bg-[#f4f7f2]"
          >
            Retry
          </button>
        ) : null}
      </div>
    </div>
  );
}

function ProtectedRouter() {
  return (
    <CommandPaletteProvider>
      <WelcomeTransition />
      <AppShell>
        <Switch>
          <Route path="/" component={DashboardPage} />
          <Route path="/assistant/new" component={AIAssistantPage} />
          <Route path="/assistant/conversations/:conversationId" component={AIAssistantPage} />
          <Route path="/assistant" component={AIAssistantPage} />
          <Route path="/knowledge/document/:documentId" component={DocumentWorkspacePage} />
          <Route path="/knowledge-center" component={KnowledgeCenterPage} />
          <Route path="/knowledge-center/:tab" component={KnowledgeCenterPage} />
          <Route path="/saved-knowledge" component={WorkspacePage} />
          <Route path="/documents" component={DocumentsPage} />
          <Route path="/knowledge" component={KnowledgeCenterPage} />
          <Route path="/policies" component={KnowledgeCenterPage} />
          <Route path="/faqs" component={FAQsPage} />
          <Route path="/experts" component={ExpertDirectoryPage} />
          <Route path="/learning" component={LearningHubPage} />
          <Route path="/knowledge-graph" component={KnowledgeGraphPage} />
          <Route path="/knowledge-gaps" component={KnowledgeGapsPage} />
          <Route path="/departments" component={DepartmentsPage} />
          <Route path="/analytics" component={AnalyticsPage} />
          <Route path="/admin/system-monitor" component={AdminSystemMonitorPage} />
          <Route path="/admin" component={AdminSettingsPage} />
          <Route path="/admin/:sub" component={AdminSettingsPage} />
          <Route path="/workspace" component={WorkspacePage} />
          <Route path="/workspace/summaries/new" component={SummaryWorkspacePage} />
          <Route path="/workspace/summaries/:id" component={SummaryWorkspacePage} />
          <Route path="/workspace/:sub" component={WorkspacePage} />
          <Route component={NotFound} />
        </Switch>
      </AppShell>
      <CommandPalette />
    </CommandPaletteProvider>
  );
}

function AuthRouter() {
  const { status, isAuthenticated, authError, refreshSession } = useAuth();
  const [location, setLocation] = useLocation();
  const isAuthRoute = location === "/login" || location === "/signup";

  useEffect(() => {
    if (status === "initializing" || status === "error") {
      return;
    }

    if (!isAuthenticated) {
      if (!isAuthRoute) {
        setPostAuthRedirect(location);
        setLocation("/login", { replace: true });
      }
      return;
    }

    if (isAuthRoute) {
      const nextLocation = consumePostAuthRedirect();
      if (nextLocation !== location) {
        setLocation(nextLocation, { replace: true });
      }
    }
  }, [isAuthRoute, isAuthenticated, location, setLocation, status]);

  if (status === "initializing") {
    return <AppBootScreen />;
  }

  if (status === "error") {
    return (
      <AppBootScreen
        message="Unable to restore your session."
        error={authError}
        onRetry={() => void refreshSession()}
      />
    );
  }

  if (!isAuthenticated) {
    if (!isAuthRoute) {
      return <AppBootScreen />;
    }
    return (
      <Switch>
        <Route path="/login" component={LoginPage} />
        <Route path="/signup" component={SignupPage} />
        <Route component={LoginPage} />
      </Switch>
    );
  }

  if (isAuthRoute) {
    return <AppBootScreen />;
  }

  return <ProtectedRouter />;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
          <AuthProvider>
            <AuthRouter />
          </AuthProvider>
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
