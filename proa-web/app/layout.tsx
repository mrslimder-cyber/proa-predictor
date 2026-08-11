import "./globals.css";
import NavLinks from "./nav-links";

export const metadata = {
  title: "ProA Predictor",
  description: "Predicciones, clasificación y estadísticas de la Pro A alemana de baloncesto",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <div className="shell">
          <div className="topbar">
            <a href="/" className="brand">
              <span className="ball">🏀</span> PROA <span>PREDICTOR</span>
            </a>
            <NavLinks />
          </div>
          {children}
          <footer>
            Datos vía Proballers · modelo XGBoost entrenado con Elo, Four Factors
            y forma reciente.
          </footer>
        </div>
      </body>
    </html>
  );
}
