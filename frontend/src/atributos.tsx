import { useEffect, useState } from "react";
import { api, type AtributoConfig } from "./api";

/**
 * Campos de los atributos adicionales activos de un documento y nivel (ADR-005).
 * Cada módulo operativo lo pone en su formulario de cabecera, línea o distribución:
 *
 *   <CamposAtributos documento="solicitud" nivel="linea" valores={linea.atributos} onCambio={...} />
 *
 * Los valores se envían a la API con la misma clave de columna (atr_texto_01…).
 */
export type ValoresAtributos = Record<string, string>;

const cache = new Map<string, Promise<AtributoConfig[]>>();

export function useAtributos(documento: string, nivel: string) {
  const [atributos, setAtributos] = useState<AtributoConfig[]>([]);
  useEffect(() => {
    if (!cache.has(documento)) cache.set(documento, api<AtributoConfig[]>(`/seguridad/atributos?documento=${documento}&solo_activos=true`));
    cache
      .get(documento)!
      .then((todos) => setAtributos(todos.filter((a) => a.nivel === nivel)))
      .catch(() => setAtributos([]));
  }, [documento, nivel]);
  return atributos;
}

/** Vacía la memoria de configuración (después de cambiarla en Administración). */
export const olvidarAtributos = () => cache.clear();

/** Valores iniciales de un documento nuevo: los valores por defecto configurados. */
export const valoresIniciales = (atributos: AtributoConfig[]): ValoresAtributos =>
  Object.fromEntries(atributos.filter((a) => a.valor_defecto).map((a) => [a.columna, a.valor_defecto as string]));

export function CamposAtributos({
  documento,
  nivel,
  valores,
  onCambio,
  deshabilitado,
}: {
  documento: string;
  nivel: string;
  valores: ValoresAtributos;
  onCambio: (v: ValoresAtributos) => void;
  deshabilitado?: boolean;
}) {
  const atributos = useAtributos(documento, nivel);
  if (atributos.length === 0) return null;
  return (
    <div className="campos-atributos">
      {atributos.map((a) => {
        const valor = valores[a.columna] ?? "";
        const cambiar = (v: string) => onCambio({ ...valores, [a.columna]: v });
        return (
          <label key={a.columna}>
            {a.etiqueta}
            {a.tipo === "texto" && a.valores.length > 0 ? (
              <select value={valor} disabled={deshabilitado} onChange={(e) => cambiar(e.target.value)}>
                <option value="">—</option>
                {a.valores.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={a.tipo === "numero" ? "number" : a.tipo === "fecha" ? "date" : "text"}
                step={a.tipo === "numero" ? "0.0001" : undefined}
                maxLength={a.tipo === "texto" ? 240 : undefined}
                value={valor}
                disabled={deshabilitado}
                onChange={(e) => cambiar(e.target.value)}
              />
            )}
            {a.ayuda && <small>{a.ayuda}</small>}
          </label>
        );
      })}
    </div>
  );
}
