import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { SiteLayout } from "./components/SiteLayout";
import { Dashboard } from "./pages/Dashboard";
import { Landing } from "./pages/Landing";
import { Learn } from "./pages/Learn";
import { Reports } from "./pages/Reports";
import { Queries } from "./pages/Queries";
import { PlacementSimulator } from "./pages/PlacementSimulator";
import { QueryDetail } from "./pages/QueryDetail";
import { Regressions } from "./pages/Regressions";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<SiteLayout />}>
            <Route path="/" element={<Landing />} />
            <Route path="/learn" element={<Learn />} />
            <Route path="/docs" element={<Navigate to="/learn" replace />} />
          </Route>

          <Route element={<Layout />}>
            <Route path="/app" element={<Dashboard />} />
            <Route path="/app/queries" element={<Queries />} />
            <Route path="/app/queries/:fid" element={<QueryDetail />} />
            <Route path="/app/queries/:fid/diagnostics" element={<QueryDetail />} />
            <Route path="/app/regressions" element={<Regressions />} />
            <Route path="/app/placement" element={<PlacementSimulator />} />
            <Route path="/app/reports" element={<Reports />} />

            <Route path="/queries/:fid" element={<Navigate to="/app/queries/:fid" replace />} />
            <Route
              path="/queries/:fid/diagnostics"
              element={<Navigate to="/app/queries/:fid/diagnostics" replace />}
            />
            <Route path="/regressions" element={<Navigate to="/app/regressions" replace />} />
            <Route path="/placement" element={<Navigate to="/app/placement" replace />} />
            <Route path="/reports" element={<Navigate to="/app/reports" replace />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
