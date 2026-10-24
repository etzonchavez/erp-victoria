import { useState, type FormEvent } from "react";
import { MensajeError } from "../componentes";
import { useSesion } from "../sesion";

export default function Ingreso() {
  const { ingresar } = useSesion();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      await ingresar(email, password);
    } catch (err) {
      setError(err);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <main className="ingreso">
      <section className="ingreso-marca">
        <p className="ingreso-nombre">Victoria</p>
        <p className="ingreso-lema">Compras, inventarios y finanzas para empresas que operan en Latinoamérica.</p>
      </section>
      <section className="ingreso-form">
        <form onSubmit={enviar} noValidate>
          <h1>Ingresa a tu empresa</h1>
          <label>
            Correo
            <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Contraseña
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <MensajeError error={error} />
          <button className="boton boton-primario" disabled={enviando || !email || !password}>
            {enviando ? "Ingresando…" : "Ingresar"}
          </button>
        </form>
      </section>
    </main>
  );
}
