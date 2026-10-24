// Cliente de la API. Toda llamada pasa por aquí para manejar token y errores.

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const CLAVE_TOKEN = "erp-victoria.token";

export type Modulo = { codigo: string; nombre: string; orden: number; activo: boolean; obligatorio: boolean };
export type Permiso = { codigo: string; modulo: string; descripcion: string };
export type RolResumen = { id: string; codigo: string; nombre: string };
export type Rol = RolResumen & { descripcion: string | null; activo: boolean; permisos: string[] };
export type Usuario = {
  id: string;
  email: string;
  nombre: string;
  activo: boolean;
  es_administrador: boolean;
  ultimo_acceso: string | null;
  roles: RolResumen[];
};
export type Sesion = { usuario: Usuario; permisos: string[]; modulos: Modulo[] };
export type EventoAuditoria = {
  id: string;
  fecha: string;
  usuario_email: string | null;
  accion: string;
  entidad: string;
  entidad_id: string | null;
  detalle: Record<string, unknown> | null;
};

export class ErrorApi extends Error {
  constructor(
    public status: number,
    public codigo: string,
    mensaje: string,
    public detalles: { campo: string; mensaje: string }[] = [],
  ) {
    super(mensaje);
  }
}

export function leerToken(): string | null {
  try {
    return localStorage.getItem(CLAVE_TOKEN);
  } catch {
    return null;
  }
}

export function guardarToken(token: string | null) {
  try {
    if (token) localStorage.setItem(CLAVE_TOKEN, token);
    else localStorage.removeItem(CLAVE_TOKEN);
  } catch {
    /* sin almacenamiento: la sesión dura lo que dure la pestaña */
  }
}

export async function api<T>(ruta: string, opciones: { metodo?: string; cuerpo?: unknown } = {}): Promise<T> {
  const token = leerToken();
  let r: Response;
  try {
    r = await fetch(`${API_URL}/api/v1${ruta}`, {
      method: opciones.metodo ?? "GET",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: opciones.cuerpo === undefined ? undefined : JSON.stringify(opciones.cuerpo),
    });
  } catch {
    throw new ErrorApi(0, "sin_conexion", "No hay conexión con el servidor. Verifica que la API esté levantada.");
  }
  const datos = await r.json().catch(() => null);
  if (!r.ok) {
    throw new ErrorApi(
      r.status,
      datos?.codigo ?? "error",
      datos?.mensaje ?? `Error ${r.status}`,
      datos?.detalles ?? [],
    );
  }
  return datos as T;
}
