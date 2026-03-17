import "./index.css";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/components/ThemeProvider";
import { Header } from "@/components/Header";
import { Home } from "@/pages/Home";
import { Insights } from "@/pages/Insights";
import { Data } from "@/pages/Data";

function AppShell() {
  return (
    <div className="flex h-screen flex-col">
      <Header />
      <main className="flex flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/data" element={<Data />} />
        </Routes>
      </main>
    </div>
  );
}

export function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
