import { useState, type FormEvent } from "react";
import { NOMBRE_PRODUCTO } from "../api";
import { BotonAccion, MensajeError } from "../componentes";
import { useSesion } from "../sesion";

export default function Ingreso() {
  const { ingresar, marca } = useSesion();
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
        <p className="ingreso-nombre">
          Victoria<span>ERP</span>
        </p>
        <p className="ingreso-lema">Compras, inventarios y finanzas para empresas que operan en Latinoamérica.</p>
      </section>
      <section className="ingreso-form">
        <form onSubmit={enviar} noValidate>
          {marca.logo_url && (
            <img className="ingreso-logo" src={marca.logo_url} alt={marca.nombre_empresa ?? "Logo de la empresa"} />
          )}
          <h1>{marca.nombre_empresa ? `Ingresa a ${marca.nombre_empresa}` : `Ingresa a ${NOMBRE_PRODUCTO}`}</h1>
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
          <BotonAccion ocupado={enviando} textoOcupado="Ingresando…">
            Ingresar
          </BotonAccion>
        </form>
      </section>
    </main>
  );
}
