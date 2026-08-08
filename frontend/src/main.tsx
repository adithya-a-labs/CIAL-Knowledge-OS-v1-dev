import { createRoot } from "react-dom/client";
import App from "./App";
import ThemeProvider from "./components/theme/ThemeProvider";
import AppErrorBoundary from "./components/common/AppErrorBoundary";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <AppErrorBoundary>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </AppErrorBoundary>,
);
