import { useEffect, useRef, type ReactNode } from "react";
import { ErrorApi } from "./api";

export function Panel({
  titulo,
  abierto,
  onCerrar,
  children,
}: {
  titulo: string;
  abierto: boolean;
  onCerrar: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!abierto) return;
    ref.current?.querySelector<HTMLElement>("input, select, textarea, button")?.focus();
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [abierto, onCerrar]);
  if (!abierto) return null;
  return (
    <div className="panel-fondo" onMouseDown={(e) => e.target === e.currentTarget && onCerrar()}>
      <aside className="panel" role="dialog" aria-modal="true" aria-label={titulo} ref={ref}>
        <header className="panel-cabecera">
          <h2>{titulo}</h2>
          <button className="boton-icono" onClick={onCerrar} aria-label="Cerrar">
            ×
          </button>
        </header>
        <div className="panel-cuerpo">{children}</div>
      </aside>
    </div>
  );
}

export function Encabezado({ titulo, descripcion, accion }: { titulo: string; descripcion: string; accion?: ReactNode }) {
  return (
    <div className="encabezado">
      <div>
        <h1>{titulo}</h1>
        <p>{descripcion}</p>
      </div>
      {accion}
    </div>
  );
}

export function MensajeError({ error }: { error: unknown }) {
  if (!error) return null;
  const texto = error instanceof Error ? error.message : "Ocurrió un error inesperado";
  const detalles = error instanceof ErrorApi ? error.detalles : [];
  return (
    <div className="aviso aviso-error" role="alert">
      <p>{texto}</p>
      {detalles.length > 0 && (
        <ul>
          {detalles.map((d) => (
            <li key={d.campo}>
              {etiquetaCampo(d.campo)}: {d.mensaje}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const CAMPOS: Record<string, string> = {
  email: "Correo",
  nombre: "Nombre",
  password: "Contraseña",
  codigo: "Código",
};
const etiquetaCampo = (c: string) => CAMPOS[c] ?? c;

export function Estado({ activo, si = "Activo", no = "Inactivo" }: { activo: boolean; si?: string; no?: string }) {
  return <span className={activo ? "estado estado-si" : "estado estado-no"}>{activo ? si : no}</span>;
}

export function Interruptor({
  activo,
  onCambio,
  deshabilitado,
  etiqueta,
}: {
  activo: boolean;
  onCambio: (v: boolean) => void;
  deshabilitado?: boolean;
  etiqueta: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      aria-label={etiqueta}
      className="interruptor"
      disabled={deshabilitado}
      onClick={() => onCambio(!activo)}
    >
      <span />
    </button>
  );
}

export const fecha = (iso: string | null) =>
  iso
    ? new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso))
    : "Nunca";
