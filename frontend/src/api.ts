// Cliente de la API. Toda llamada pasa por aquí para manejar token y errores.

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const CLAVE_TOKEN = "erp-victoria.token";

export const NOMBRE_PRODUCTO = "Victoria ERP";

export type Modulo = {
  codigo: string;
  nombre: string;
  abreviatura: string;
  orden: number;
  activo: boolean;
  obligatorio: boolean;
};
export type Marca = { nombre_empresa: string | null; logo_url: string | null };
export type Permiso = { codigo: string; modulo: string; descripcion: string };
export type TipoRol = { codigo: string; descripcion: string };
export type RolResumen = { id: string; codigo: string; nombre: string; tipo: string };
export type Rol = RolResumen & { modulo: string; estandar: boolean; descripcion: string | null; activo: boolean; permisos: string[] };

// Maestros
export type Pais = { codigo: string; nombre: string; moneda: string; nombre_identificacion_fiscal: string };
export type UnidadNegocio = { id: string; empresa_id: string; codigo: string; nombre: string; activo: boolean };
export type Empresa = {
  id: string;
  pais: string;
  identificacion_fiscal: string;
  razon_social: string;
  nombre_comercial: string | null;
  direccion_fiscal: string | null;
  moneda_funcional: string;
  activo: boolean;
  unidades: UnidadNegocio[];
};
export type Moneda = { codigo: string; nombre: string; simbolo: string; decimales: number; activo: boolean };
export type TipoCambio = {
  id: string;
  moneda: string;
  moneda_base: string;
  fecha: string;
  compra: string;
  venta: string;
  fuente: string;
  actualizado_en: string;
};
export type UnidadMedida = { codigo: string; nombre: string; codigo_oficial: string; tipo: string; activo: boolean };
export type Conversion = { id: string; origen: string; destino: string; factor: string };

// Contabilidad base
export type CuentaResumen = { id: string; codigo: string; nombre: string };
export type Cuenta = CuentaResumen & {
  padre_id: string | null;
  nivel: number;
  naturaleza: string;
  imputable: boolean;
  plantilla: string;
  activo: boolean;
};
export type PerfilContable = {
  id: string;
  codigo: string;
  nombre: string;
  tipo_articulo: string;
  cuenta_cargo: CuentaResumen;
  cuenta_existencia: CuentaResumen | null;
  cuenta_variacion: CuentaResumen | null;
  cuenta_por_pagar: CuentaResumen;
  activo: boolean;
};
export type CentroCosto = {
  id: string;
  unidad_negocio_id: string;
  codigo: string;
  nombre: string;
  responsable: string | null;
  activo: boolean;
};
export type Impuesto = { id: string; codigo: string; nombre: string; tasa: string; cuenta: CuentaResumen | null; activo: boolean };

export type Categoria = { id: string; codigo: string; nombre: string; padre_id: string | null; nivel: number; activo: boolean };
export type PerfilResumen = { id: string; codigo: string; nombre: string; tipo_articulo: string };
export type CategoriaPerfil = {
  categoria_id: string;
  perfil_propio: PerfilResumen | null;
  perfil_efectivo: PerfilResumen | null;
  heredado_de: { id: string; codigo: string; nombre: string } | null;
};

// Proveedores
export type CondicionPago = { id: string; codigo: string; nombre: string; dias: number; activo: boolean };
export type TipoDocumento = { codigo: string; nombre: string; codigo_oficial: string; extranjero: boolean };
export type ContactoProveedor = {
  id: string;
  nombre: string;
  cargo: string | null;
  correo: string | null;
  telefono: string | null;
  principal: boolean;
};
export type CuentaBancaria = {
  id: string;
  banco: string;
  tipo: string;
  moneda: string;
  numero: string;
  cci: string | null;
  swift: string | null;
  activo: boolean;
  enmascarada: boolean;
};
export type ProveedorResumen = {
  id: string;
  tipo_documento: string;
  numero_documento: string;
  pais: string;
  razon_social: string;
  nombre_comercial: string | null;
  moneda: string;
  condicion_pago: CondicionPago;
  activo: boolean;
  bloqueos: { empresa_id: string; motivo: string }[];
};
export type Proveedor = ProveedorResumen & {
  direccion: string | null;
  correo: string | null;
  telefono: string | null;
  contactos: ContactoProveedor[];
  cuentas: CuentaBancaria[];
  categorias: Categoria[];
};
export const NOMBRE_TIPO_CUENTA: Record<string, string> = {
  corriente: "Corriente",
  ahorros: "Ahorros",
  detracciones: "Detracciones",
};
/** Nombre del país en español a partir del código ISO de 2 letras. */
export const nombrePais = (codigo: string) => {
  try {
    return new Intl.DisplayNames(["es"], { type: "region" }).of(codigo.toUpperCase()) ?? codigo.toUpperCase();
  } catch {
    return codigo.toUpperCase();
  }
};

// Artículos
export type ArticuloResumen = {
  id: string;
  codigo: string;
  descripcion: string;
  tipo: string;
  categoria: Categoria;
  unidad: string;
  precio_referencial: string | null;
  moneda_precio: string | null;
  activo: boolean;
};
export type Articulo = ArticuloResumen & {
  impuesto: string;
  marca: string | null;
  modelo: string | null;
  especificacion: string | null;
  unidades_alternas: { unidad: string; factor: string }[];
};
export type EstadoContable = {
  empresa_id: string;
  razon_social: string;
  perfil: PerfilContable | null;
  origen: string | null;
  excepcion: boolean;
  impuesto: { codigo: string; nombre: string; tasa: string } | null;
  problema: string | null;
};

// Atributos adicionales (ADR-005)
export type DocumentoOperativo = { codigo: string; nombre: string; niveles: string[]; destinos: string[] };
export type AtributoConfig = {
  documento: string;
  nivel: string;
  tipo: "texto" | "numero" | "fecha";
  numero: number;
  columna: string;
  activo: boolean;
  etiqueta: string | null;
  ayuda: string | null;
  valor_defecto: string | null;
  valores: string[];
  copiar_documento: string | null;
  copiar_numero: number | null;
};
export const NOMBRE_NIVEL: Record<string, string> = { cabecera: "Cabecera", linea: "Línea", distribucion: "Distribución" };
export const NOMBRE_TIPO_ATRIBUTO: Record<string, string> = { texto: "Texto", numero: "Número", fecha: "Fecha" };

export const NOMBRE_TIPO_ARTICULO: Record<string, string> = {
  bien_inventariable: "Bien inventariable",
  bien_no_inventariable: "Bien no inventariable",
  servicio: "Servicio",
  activo_fijo: "Activo fijo",
};
export const NOMBRE_NATURALEZA: Record<string, string> = {
  activo: "Activo",
  pasivo: "Pasivo",
  patrimonio: "Patrimonio",
  gasto: "Gasto",
  ingreso: "Ingreso",
  resultado: "Resultado",
  analitica: "Analítica",
  orden: "Orden",
};
/** Igual que REGLAS_PERFIL del backend: naturaleza permitida de cada cuenta; null = no aplica. */
export const REGLAS_PERFIL: Record<string, Record<"cargo" | "existencia" | "variacion" | "por_pagar", string[] | null>> = {
  bien_inventariable: { cargo: ["gasto"], existencia: ["activo"], variacion: ["gasto"], por_pagar: ["pasivo"] },
  bien_no_inventariable: { cargo: ["gasto"], existencia: null, variacion: null, por_pagar: ["pasivo"] },
  servicio: { cargo: ["gasto"], existencia: null, variacion: null, por_pagar: ["pasivo"] },
  activo_fijo: { cargo: ["activo"], existencia: null, variacion: null, por_pagar: ["pasivo"] },
};
export const cuentaTexto = (c: CuentaResumen | null) => (c ? `${c.codigo} ${c.nombre}` : "—");

export const NOMBRE_TIPO_UNIDAD: Record<string, string> = {
  cantidad: "Cantidad",
  servicio: "Servicio",
  peso: "Peso",
  volumen: "Volumen",
  longitud: "Longitud",
  area: "Área",
  tiempo: "Tiempo",
};

/** Fecha local de hoy en formato AAAA-MM-DD (no UTC: en Lima a las 8 p. m. ya sería mañana en UTC). */
export const hoyLocal = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

/** Quita ceros sobrantes de un decimal que llega como texto: "3.720000" → "3.72". */
export const decimal = (v: string) => (v.includes(".") ? v.replace(/0+$/, "").replace(/\.$/, "") : v);

export const NOMBRE_TIPO: Record<string, string> = {
  administrador: "Administrador",
  configuracion: "Configuración",
  operativo: "Operativo",
  consulta: "Consulta",
};
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

export async function api<T>(
  ruta: string,
  opciones: {
    metodo?: string;
    cuerpo?: unknown;
    archivo?: { campo: string; valor: File };
    campos?: Record<string, string>;
  } = {},
): Promise<T> {
  const token = leerToken();
  let body: BodyInit | undefined;
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
  if (opciones.archivo) {
    // Formulario multipart: el navegador pone el Content-Type con su separador
    const form = new FormData();
    form.append(opciones.archivo.campo, opciones.archivo.valor);
    for (const [k, v] of Object.entries(opciones.campos ?? {})) form.append(k, v);
    body = form;
  } else if (opciones.cuerpo !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opciones.cuerpo);
  }
  let r: Response;
  try {
    r = await fetch(`${API_URL}/api/v1${ruta}`, { method: opciones.metodo ?? "GET", headers, body });
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

/** Descarga un archivo de la API (con la sesión del usuario) y lo guarda en el equipo. */
export async function descargar(ruta: string, nombre: string): Promise<void> {
  const token = leerToken();
  const r = await fetch(`${API_URL}/api/v1${ruta}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!r.ok) {
    const datos = await r.json().catch(() => null);
    throw new ErrorApi(r.status, datos?.codigo ?? "error", datos?.mensaje ?? `Error ${r.status}`);
  }
  const url = URL.createObjectURL(await r.blob());
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(url);
}
