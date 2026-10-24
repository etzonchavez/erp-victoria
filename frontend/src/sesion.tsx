import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ErrorApi, guardarToken, leerToken, type Sesion } from "./api";

type Contexto = {
  sesion: Sesion | null;
  cargando: boolean;
  ingresar: (email: string, password: string) => Promise<void>;
  salir: () => void;
  recargar: () => Promise<void>;
  puede: (permiso: string) => boolean;
};

const SesionContext = createContext<Contexto | null>(null);

export function SesionProvider({ children }: { children: ReactNode }) {
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [cargando, setCargando] = useState(true);

  const recargar = useCallback(async () => {
    if (!leerToken()) {
      setSesion(null);
      setCargando(false);
      return;
    }
    try {
      setSesion(await api<Sesion>("/seguridad/auth/sesion"));
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 401) guardarToken(null);
      setSesion(null);
    } finally {
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    recargar();
  }, [recargar]);

  const ingresar = async (email: string, password: string) => {
    const { access_token } = await api<{ access_token: string }>("/seguridad/auth/login", {
      metodo: "POST",
      cuerpo: { email, password },
    });
    guardarToken(access_token);
    await recargar();
  };

  const salir = () => {
    guardarToken(null);
    setSesion(null);
  };

  const puede = useCallback((permiso: string) => sesion?.permisos.includes(permiso) ?? false, [sesion]);

  return (
    <SesionContext.Provider value={{ sesion, cargando, ingresar, salir, recargar, puede }}>
      {children}
    </SesionContext.Provider>
  );
}

export function useSesion() {
  const ctx = useContext(SesionContext);
  if (!ctx) throw new Error("useSesion fuera de SesionProvider");
  return ctx;
}
