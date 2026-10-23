import { useEffect, useState } from "react";

type Health = {
  status: string;
  app: string;
  version: string;
  environment: string;
  database: string;
};

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setError(true));
  }, []);

  return (
    <main className="shell">
      <header>
        <h1>ERP Victoria</h1>
        <p>Plataforma en construcción · Semana 1</p>
      </header>
      <section className="card">
        <h2>Estado del sistema</h2>
        {error && <p className="bad">La API no responde.</p>}
        {!error && !health && <p>Consultando…</p>}
        {health && (
          <dl>
            <dt>API</dt>
            <dd className="ok">{health.status}</dd>
            <dt>Base de datos</dt>
            <dd className={health.database === "ok" ? "ok" : "bad"}>{health.database}</dd>
            <dt>Versión</dt>
            <dd>{health.version}</dd>
            <dt>Ambiente</dt>
            <dd>{health.environment}</dd>
          </dl>
        )}
      </section>
    </main>
  );
}
