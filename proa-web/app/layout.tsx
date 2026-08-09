import "./globals.css";

export const metadata = {
  title: "ProA Predictor",
  description: "Predicciones de la Pro A alemana de baloncesto",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <div className="shell">
          <div className="topbar">
            <div className="brand">
              PROA <span>PREDICTOR</span>
            </div>
            <nav>
              <a href="/">Próximos partidos</a>
              <a href="/clasificacion">Clasificación Elo</a>
            </nav>
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
