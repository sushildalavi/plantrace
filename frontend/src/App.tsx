import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { SiteLayout } from "./components/SiteLayout";
import { Skeleton } from "./components/Section";

const Dashboard = lazy(() => import("./pages/Dashboard").then((m) => ({ default: m.Dashboard })));
const Landing = lazy(() => import("./pages/Landing").then((m) => ({ default: m.Landing })));
const Learn = lazy(() => import("./pages/Learn").then((m) => ({ default: m.Learn })));
const Reports = lazy(() => import("./pages/Reports").then((m) => ({ default: m.Reports })));
const Queries = lazy(() => import("./pages/Queries").then((m) => ({ default: m.Queries })));
const PlacementSimulator = lazy(() =>
  import("./pages/PlacementSimulator").then((m) => ({ default: m.PlacementSimulator }))
);
const QueryDetail = lazy(() => import("./pages/QueryDetail").then((m) => ({ default: m.QueryDetail })));
const Regressions = lazy(() => import("./pages/Regressions").then((m) => ({ default: m.Regressions })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 30_000 },
  },
});

function RouteFallback() {
  return (
    <div className="space-y-4">
      <Skeleton className="h-10 w-1/3" />
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Suspense fallback={<RouteFallback />}>
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
      </Suspense>
    </QueryClientProvider>
  );
}
