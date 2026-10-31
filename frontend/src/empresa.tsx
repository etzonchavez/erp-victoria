import { useCallback, useEffect, useState } from "react";
import { api, type UnidadNegocio } from "./api";

/** Empresa con la que trabaja el usuario en las pantallas que dependen de una empresa. */
export type EmpresaResumen = {
  id: string;
  pais: string;
  identificacion_fiscal: string;
  razon_social: string;
  moneda_funcional: string;
  unidades: UnidadNegocio[];
};

const CLAVE = "victoria.empresa";

const leer = () => {
  try {
    return localStorage.getItem(CLAVE);
  } catch {
    return null;
  }
};

export function useEmpresaActiva() {
  const [empresas, setEmpresas] = useState<EmpresaResumen[]>([]);
  const [id, setId] = useState<string | null>(leer);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    api<EmpresaResumen[]>("/maestros/empresas/accesibles")
      .then(setEmpresas)
      .catch(setError)
      .finally(() => setCargando(false));
  }, []);

  const elegir = useCallback((nuevo: string) => {
    setId(nuevo);
    try {
      localStorage.setItem(CLAVE, nuevo);
    } catch {
      /* sin almacenamiento: se recuerda solo en esta pestaña */
    }
  }, []);

  const empresa = empresas.find((e) => e.id === id) ?? empresas[0] ?? null;
  return { empresas, empresa, elegir, cargando, error };
}

export function SelectorEmpresa({
  empresas,
  empresa,
  elegir,
}: {
  empresas: EmpresaResumen[];
  empresa: EmpresaResumen | null;
  elegir: (id: string) => void;
}) {
  if (!empresa) return null;
  if (empresas.length === 1)
    return (
      <p className="empresa-fija">
        <span className="tenue">Empresa</span> {empresa.razon_social}
      </p>
    );
  return (
    <label className="filtro selector-empresa">
      Empresa
      <select value={empresa.id} onChange={(e) => elegir(e.target.value)}>
        {empresas.map((e) => (
          <option key={e.id} value={e.id}>
            {e.razon_social}
          </option>
        ))}
      </select>
    </label>
  );
}

export function SinEmpresa({ cargando }: { cargando: boolean }) {
  if (cargando) return null;
  return (
    <div className="vacio">
      <p>
        Aún no hay empresas activas. Crea una en <a href="#/empresas">Maestros → Empresas</a>; al crearla se carga su
        plan de cuentas.
      </p>
    </div>
  );
}
