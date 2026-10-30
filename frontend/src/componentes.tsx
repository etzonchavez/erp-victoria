import { useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
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
  ocupado,
  etiqueta,
}: {
  activo: boolean;
  onCambio: (v: boolean) => void;
  deshabilitado?: boolean;
  ocupado?: boolean;
  etiqueta: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={activo}
      aria-label={etiqueta}
      className={ocupado ? "interruptor interruptor-ocupado" : "interruptor"}
      disabled={deshabilitado || ocupado}
      aria-busy={ocupado || undefined}
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

/**
 * Botón de acción con estados claros, para usar en todas las pantallas:
 * - ocupado: muestra un indicador giratorio y el texto en curso ("Guardando…").
 * - listo: tras guardar muestra "✓ Guardado" unos segundos y vuelve a su estado normal.
 * Nunca queda gris sin explicación: el gris (deshabilitado) se reserva para
 * cuando la acción no está permitida.
 */
export function BotonAccion({
  ocupado = false,
  textoOcupado = "Guardando…",
  listo = false,
  textoListo = "Guardado",
  primario = true,
  className,
  children,
  disabled,
  ...resto
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  ocupado?: boolean;
  textoOcupado?: string;
  listo?: boolean;
  textoListo?: string;
  primario?: boolean;
}) {
  const clases = ["boton", primario && "boton-primario", ocupado && "boton-ocupado", listo && !ocupado && "boton-listo", className]
    .filter(Boolean)
    .join(" ");
  return (
    <button {...resto} className={clases} disabled={disabled || ocupado} aria-busy={ocupado || undefined}>
      {ocupado ? (
        <>
          <span className="giro" aria-hidden="true" /> {textoOcupado}
        </>
      ) : listo ? (
        <>
          <span aria-hidden="true">✓</span> {textoListo}
        </>
      ) : (
        children
      )}
    </button>
  );
}

/** Marca "listo" durante unos segundos después de una acción exitosa. */
export function useConfirmacion(duracion = 2500) {
  const [listo, setListo] = useState(false);
  const temporizador = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(temporizador.current), []);
  const confirmar = () => {
    setListo(true);
    window.clearTimeout(temporizador.current);
    temporizador.current = window.setTimeout(() => setListo(false), duracion);
  };
  return { listo, confirmar, reiniciar: () => setListo(false) };
}

/** Fecha sin hora (AAAA-MM-DD) mostrada en español, sin desfase de zona horaria. */
export const fechaDia = (iso: string) => {
  const [a, m, d] = iso.split("-").map(Number);
  return new Intl.DateTimeFormat("es-PE", { dateStyle: "medium" }).format(new Date(a, m - 1, d));
};
