import { Switch, Route, Router as WouterRouter } from "wouter";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import AppShell from "@/components/layout/AppShell";
import DashboardPage from "@/pages/DashboardPage";
import AIAssistantPage from "@/pages/AIAssistantPage";
import KnowledgeCenterPage from "@/pages/KnowledgeCenterPage";
import DocumentsPage from "@/pages/DocumentsPage";
import FAQsPage from "@/pages/FAQsPage";
import ExpertDirectoryPage from "@/pages/ExpertDirectoryPage";
import LearningHubPage from "@/pages/LearningHubPage";
import KnowledgeGraphPage from "@/pages/KnowledgeGraphPage";
import KnowledgeGapsPage from "@/pages/KnowledgeGapsPage";
import DepartmentsPage from "@/pages/DepartmentsPage";
import AnalyticsPage from "@/pages/AnalyticsPage";
import AdminSettingsPage from "@/pages/AdminSettingsPage";
import WorkspacePage from "@/pages/WorkspacePage";
import NotFound from "@/pages/not-found";

const queryClient = new QueryClient();

function Router() {
  return (
    <AppShell>
      <Switch>
        <Route path="/" component={DashboardPage} />
        <Route path="/assistant" component={AIAssistantPage} />
        <Route path="/knowledge-center" component={KnowledgeCenterPage} />
        <Route path="/knowledge-center/:tab" component={KnowledgeCenterPage} />
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
        <Route path="/admin" component={AdminSettingsPage} />
        <Route path="/admin/:sub" component={AdminSettingsPage} />
        <Route path="/workspace" component={WorkspacePage} />
        <Route path="/workspace/:sub" component={WorkspacePage} />
        <Route component={NotFound} />
      </Switch>
    </AppShell>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, "")}>
          <Router />
        </WouterRouter>
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>
  );
}

export default App;
