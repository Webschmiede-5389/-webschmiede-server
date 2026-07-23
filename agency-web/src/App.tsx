import { Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import ImpressumPage from "./pages/ImpressumPage";
import DatenschutzPage from "./pages/DatenschutzPage";
import MarkenhinweisePage from "./pages/MarkenhinweisePage";
import SupportPage from "./pages/SupportPage";
import AnbindungenPage from "./pages/AnbindungenPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/anbindungen" element={<AnbindungenPage />} />
      <Route path="/impressum" element={<ImpressumPage />} />
      <Route path="/datenschutz" element={<DatenschutzPage />} />
      <Route path="/markenhinweise" element={<MarkenhinweisePage />} />
      <Route path="/support" element={<SupportPage />} />
    </Routes>
  );
}
