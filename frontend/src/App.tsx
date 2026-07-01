import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
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
        <Layout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/queries/:fid" element={<QueryDetail />} />
            <Route path="/queries/:fid/diagnostics" element={<QueryDetail />} />
            <Route path="/regressions" element={<Regressions />} />
            <Route path="/placement" element={<PlacementSimulator />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
