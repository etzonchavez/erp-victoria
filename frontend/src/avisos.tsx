import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";

/**
 * Notificaciones breves de confirmación ("Usuario guardado", "Módulo activado").
 * Se usan después de cualquier acción que guarda datos, para que el usuario
 * siempre sepa que su cambio quedó registrado aunque el panel se cierre.
 */
type Aviso = { id: number; texto: string };
type Contexto = { avisar: (texto: string) => void };

const AvisosContext = createContext<Contexto | null>(null);
const DURACION = 3500;

export function AvisosProvider({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const siguiente = useRef(0);

  const avisar = useCallback((texto: string) => {
    const id = ++siguiente.current;
    setAvisos((a) => [...a.slice(-2), { id, texto }]);
    window.setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== id)), DURACION);
  }, []);

  return (
    <AvisosContext.Provider value={{ avisar }}>
      {children}
      <div className="notificaciones" role="status" aria-live="polite">
        {avisos.map((a) => (
          <p key={a.id} className="notificacion">
            <span aria-hidden="true">✓</span> {a.texto}
          </p>
        ))}
      </div>
    </AvisosContext.Provider>
  );
}

export function useAvisos() {
  const ctx = useContext(AvisosContext);
  if (!ctx) throw new Error("useAvisos fuera de AvisosProvider");
  return ctx;
}
