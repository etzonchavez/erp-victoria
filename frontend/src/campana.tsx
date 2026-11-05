import { Bell, CheckCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { fecha } from "./componentes";

type Notificacion = { id: string; tipo: string; titulo: string; mensaje: string; enlace: string; creado_en: string; leida_en: string | null };
type Respuesta = { no_leidas: number; items: Notificacion[] };

const CADA_MS = 60_000;

/** Campana de la barra superior: contador de no leídas y panel con los avisos. */
export function Campana() {
  const [datos, setDatos] = useState<Respuesta>({ no_leidas: 0, items: [] });
  const [abierta, setAbierta] = useState(false);
  const caja = useRef<HTMLDivElement>(null);

  const cargar = useCallback(() => {
    api<Respuesta>("/seguridad/notificaciones")
      .then(setDatos)
      .catch(() => null);
  }, []);
  useEffect(() => {
    cargar();
    const intervalo = window.setInterval(cargar, CADA_MS);
    window.addEventListener("hashchange", cargar);
    window.addEventListener("focus", cargar);
    return () => {
      window.clearInterval(intervalo);
      window.removeEventListener("hashchange", cargar);
      window.removeEventListener("focus", cargar);
    };
  }, [cargar]);
  useEffect(() => {
    if (!abierta) return;
    const fuera = (e: MouseEvent) => {
      if (caja.current && !caja.current.contains(e.target as Node)) setAbierta(false);
    };
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && setAbierta(false);
    document.addEventListener("mousedown", fuera);
    window.addEventListener("keydown", tecla);
    return () => {
      document.removeEventListener("mousedown", fuera);
      window.removeEventListener("keydown", tecla);
    };
  }, [abierta]);

  const abrir = async (n: Notificacion) => {
    setAbierta(false);
    if (!n.leida_en) await api(`/seguridad/notificaciones/${n.id}/leida`, { metodo: "POST" }).catch(() => null);
    window.location.hash = `#/${n.enlace}`;
    cargar();
  };
  const leerTodas = async () => {
    await api("/seguridad/notificaciones/leidas", { metodo: "POST" }).catch(() => null);
    cargar();
  };

  return (
    <div className="campana" ref={caja}>
      <button
        className="boton-icono"
        onClick={() => {
          setAbierta(!abierta);
          if (!abierta) cargar();
        }}
        aria-expanded={abierta}
        aria-label={datos.no_leidas ? `Notificaciones: ${datos.no_leidas} sin leer` : "Notificaciones"}
      >
        <Bell size={20} />
        {datos.no_leidas > 0 && <span className="campana-contador">{datos.no_leidas > 99 ? "99+" : datos.no_leidas}</span>}
      </button>
      {abierta && (
        <div className="campana-panel" role="dialog" aria-label="Notificaciones">
          <header>
            <strong>Notificaciones</strong>
            {datos.no_leidas > 0 && (
              <button onClick={leerTodas}>
                <CheckCheck size={16} aria-hidden="true" /> Marcar todas como leídas
              </button>
            )}
          </header>
          {datos.items.length === 0 ? (
            <p className="tenue campana-vacia">No tienes notificaciones.</p>
          ) : (
            <ul>
              {datos.items.map((n) => (
                <li key={n.id}>
                  <button className={n.leida_en ? "aviso-item" : "aviso-item no-leido"} onClick={() => abrir(n)}>
                    <span className={`aviso-punto aviso-${n.tipo}`} aria-hidden="true" />
                    <span>
                      <strong>{n.titulo}</strong>
                      <span>{n.mensaje}</span>
                      <small>{fecha(n.creado_en)}</small>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
