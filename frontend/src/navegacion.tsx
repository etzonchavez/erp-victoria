import type { LucideIcon } from "lucide-react";
import {
  BadgeDollarSign,
  BookOpen,
  CalendarClock,
  FileBarChart,
  Building2,
  ClipboardList,
  FileSpreadsheet,
  FileText,
  FolderTree,
  Handshake,
  Landmark,
  LayoutGrid,
  ListChecks,
  Package,
  Palette,
  Percent,
  Puzzle,
  Receipt,
  Ruler,
  ScrollText,
  Settings,
  ShieldCheck,
  ShoppingCart,
  SlidersHorizontal,
  Target,
  Truck,
  UserCog,
  Users,
  Wallet,
} from "lucide-react";
import type { ReactNode } from "react";
import Articulos from "./paginas/Articulos";
import Atributos from "./paginas/Atributos";
import Auditoria from "./paginas/Auditoria";
import CargaExcel from "./paginas/CargaExcel";
import Categorias from "./paginas/Categorias";
import CentrosCosto from "./paginas/CentrosCosto";
import CondicionesPago from "./paginas/CondicionesPago";
import Empresas from "./paginas/Empresas";
import FormatoOrden from "./paginas/FormatoOrden";
import Impuestos from "./paginas/Impuestos";
import Modulos from "./paginas/Modulos";
import Monedas from "./paginas/Monedas";
import OrdenesCompra from "./paginas/OrdenesCompra";
import PerfilesContables from "./paginas/PerfilesContables";
import Personalizacion from "./paginas/Personalizacion";
import PlanCuentas from "./paginas/PlanCuentas";
import Proveedores from "./paginas/Proveedores";
import ReconocimientoCargo from "./paginas/ReconocimientoCargo";
import ReporteCompras from "./paginas/ReporteCompras";
import ReglasAprobacion from "./paginas/ReglasAprobacion";
import Roles from "./paginas/Roles";
import Solicitudes from "./paginas/Solicitudes";
import Unidades from "./paginas/Unidades";
import Usuarios from "./paginas/Usuarios";

/**
 * Registro único de pantallas. Una pantalla nueva se agrega aquí una sola vez y aparece sola
 * en Inicio o en Configuración y en el menú lateral, si el módulo está activo y el usuario
 * tiene alguno de sus permisos (sin permiso = todo usuario del módulo).
 *
 * - tipo "tarea": trabajo del día a día; va en Inicio, agrupada por módulo.
 * - tipo "configuracion": va en Configuración, agrupada por área.
 */
export type Pantalla = {
  ruta: string;
  nombre: string;
  descripcion: string;
  modulo: string | string[]; // varios: visible si alguno está activo
  icono: LucideIcon;
  tipo: "tarea" | "configuracion";
  area?: string; // solo configuración
  permiso?: string | string[];
  pagina: () => ReactNode;
};

/** Ícono y orden de los módulos en Inicio y en el menú. */
export const MODULOS: { codigo: string; icono: LucideIcon }[] = [
  { codigo: "solicitudes", icono: ClipboardList },
  { codigo: "compras", icono: ShoppingCart },
  { codigo: "maestros", icono: Package },
  { codigo: "contabilidad", icono: Landmark },
  { codigo: "seguridad", icono: ShieldCheck },
];

/** Áreas de Configuración, en orden. */
export const AREAS: { codigo: string; nombre: string; icono: LucideIcon }[] = [
  { codigo: "organizacion", nombre: "Organización", icono: Building2 },
  { codigo: "catalogos", nombre: "Catálogos", icono: FolderTree },
  { codigo: "contabilidad", nombre: "Contabilidad", icono: Landmark },
  { codigo: "cxp", nombre: "Cuentas por pagar", icono: Receipt },
  { codigo: "documentos", nombre: "Aprobaciones y documentos", icono: ListChecks },
  { codigo: "seguridad", nombre: "Seguridad y sistema", icono: ShieldCheck },
];

export const ICONO_INICIO = LayoutGrid;
export const ICONO_CONFIGURACION = Settings;

export const PANTALLAS: Pantalla[] = [
  // ---------------------------------------------------------------- tareas
  {
    ruta: "solicitudes",
    nombre: "Solicitudes de compra",
    descripcion: "Pide lo que necesitas y sigue su aprobación",
    modulo: "solicitudes",
    icono: ClipboardList,
    tipo: "tarea",
    pagina: () => <Solicitudes />,
  },
  {
    ruta: "ordenes-compra",
    nombre: "Órdenes de compra",
    descripcion: "Emite, aprueba y envía órdenes al proveedor",
    modulo: "compras",
    icono: ShoppingCart,
    tipo: "tarea",
    pagina: () => <OrdenesCompra />,
  },
  {
    ruta: "reporte-compras",
    nombre: "Reporte de compras",
    descripcion: "Excel de solicitudes y órdenes con filtros",
    modulo: "compras",
    icono: FileBarChart,
    tipo: "tarea",
    permiso: "compras.orden.ver",
    pagina: () => <ReporteCompras />,
  },
  {
    ruta: "articulos",
    nombre: "Artículos",
    descripcion: "Bienes y servicios que se compran",
    modulo: "maestros",
    icono: Package,
    tipo: "tarea",
    permiso: "maestros.articulo.ver",
    pagina: () => <Articulos />,
  },
  {
    ruta: "proveedores",
    nombre: "Proveedores",
    descripcion: "Datos, contactos y bloqueos por empresa",
    modulo: "maestros",
    icono: Truck,
    tipo: "tarea",
    permiso: "maestros.proveedor.ver",
    pagina: () => <Proveedores />,
  },
  // ---------------------------------------------------------------- configuración: organización
  {
    ruta: "empresas",
    nombre: "Empresas",
    descripcion: "Empresas del grupo y sus unidades de negocio",
    modulo: "maestros",
    icono: Building2,
    tipo: "configuracion",
    area: "organizacion",
    permiso: "maestros.empresa.ver",
    pagina: () => <Empresas />,
  },
  {
    ruta: "monedas",
    nombre: "Monedas y tipo de cambio",
    descripcion: "Monedas activas y tipo de cambio diario",
    modulo: "maestros",
    icono: BadgeDollarSign,
    tipo: "configuracion",
    area: "organizacion",
    permiso: "maestros.moneda.ver",
    pagina: () => <Monedas />,
  },
  {
    ruta: "unidades",
    nombre: "Unidades de medida",
    descripcion: "Unidades con su código SUNAT",
    modulo: "maestros",
    icono: Ruler,
    tipo: "configuracion",
    area: "organizacion",
    permiso: "maestros.unidad.ver",
    pagina: () => <Unidades />,
  },
  // ---------------------------------------------------------------- catálogos
  {
    ruta: "categorias",
    nombre: "Categorías de artículo",
    descripcion: "Árbol de categorías y su perfil contable",
    modulo: "maestros",
    icono: FolderTree,
    tipo: "configuracion",
    area: "catalogos",
    permiso: "maestros.categoria.ver",
    pagina: () => <Categorias />,
  },
  {
    ruta: "condiciones-pago",
    nombre: "Condiciones de pago",
    descripcion: "Contado y créditos para proveedores",
    modulo: "maestros",
    icono: Handshake,
    tipo: "configuracion",
    area: "catalogos",
    permiso: "maestros.proveedor.ver",
    pagina: () => <CondicionesPago />,
  },
  {
    ruta: "carga-excel",
    nombre: "Carga desde Excel",
    descripcion: "Artículos, proveedores, categorías y plan de cuentas",
    modulo: "maestros",
    icono: FileSpreadsheet,
    tipo: "configuracion",
    area: "catalogos",
    permiso: ["maestros.categoria.editar", "maestros.articulo.crear", "maestros.proveedor.crear", "contabilidad.cuenta.editar"],
    pagina: () => <CargaExcel />,
  },
  // ---------------------------------------------------------------- contabilidad
  {
    ruta: "plan-cuentas",
    nombre: "Plan de cuentas",
    descripcion: "Cuentas contables de cada empresa",
    modulo: "contabilidad",
    icono: BookOpen,
    tipo: "configuracion",
    area: "contabilidad",
    permiso: "contabilidad.cuenta.ver",
    pagina: () => <PlanCuentas />,
  },
  {
    ruta: "perfiles",
    nombre: "Perfiles contables",
    descripcion: "Cuentas que usa cada tipo de compra",
    modulo: "contabilidad",
    icono: Wallet,
    tipo: "configuracion",
    area: "contabilidad",
    permiso: "contabilidad.perfil.ver",
    pagina: () => <PerfilesContables />,
  },
  {
    ruta: "centros-costo",
    nombre: "Centros de costo",
    descripcion: "Centros y sus responsables",
    modulo: "contabilidad",
    icono: Target,
    tipo: "configuracion",
    area: "contabilidad",
    permiso: "contabilidad.centro_costo.ver",
    pagina: () => <CentrosCosto />,
  },
  {
    ruta: "impuestos",
    nombre: "Impuestos",
    descripcion: "IGV y otros impuestos de la empresa",
    modulo: "contabilidad",
    icono: Percent,
    tipo: "configuracion",
    area: "contabilidad",
    permiso: "contabilidad.impuesto.ver",
    pagina: () => <Impuestos />,
  },
  // ---------------------------------------------------------------- cuentas por pagar
  {
    ruta: "reconocimiento-cargo",
    nombre: "Reconocimiento del cargo",
    descripcion: "Al recibir o al facturar, por tipo de artículo",
    modulo: "contabilidad",
    icono: CalendarClock,
    tipo: "configuracion",
    area: "cxp",
    permiso: "contabilidad.cxp.ver",
    pagina: () => <ReconocimientoCargo />,
  },
  // ---------------------------------------------------------------- aprobaciones y documentos
  {
    ruta: "reglas-aprobacion",
    nombre: "Reglas de aprobación",
    descripcion: "Quién aprueba solicitudes y órdenes",
    modulo: ["solicitudes", "compras"],
    icono: ListChecks,
    tipo: "configuracion",
    area: "documentos",
    permiso: ["solicitudes.regla.ver", "compras.regla.ver"],
    pagina: () => <ReglasAprobacion />,
  },
  {
    ruta: "formato-oc",
    nombre: "Formato de la orden",
    descripcion: "Logo, color y datos del PDF de la orden",
    modulo: "compras",
    icono: FileText,
    tipo: "configuracion",
    area: "documentos",
    permiso: "compras.formato.editar",
    pagina: () => <FormatoOrden />,
  },
  {
    ruta: "atributos",
    nombre: "Atributos adicionales",
    descripcion: "Campos propios en cabecera, línea y distribución",
    modulo: "seguridad",
    icono: SlidersHorizontal,
    tipo: "configuracion",
    area: "documentos",
    permiso: "seguridad.atributo.editar",
    pagina: () => <Atributos />,
  },
  // ---------------------------------------------------------------- seguridad y sistema
  {
    ruta: "usuarios",
    nombre: "Usuarios",
    descripcion: "Accesos, roles y empresas de cada usuario",
    modulo: "seguridad",
    icono: Users,
    tipo: "configuracion",
    area: "seguridad",
    permiso: "seguridad.usuario.ver",
    pagina: () => <Usuarios />,
  },
  {
    ruta: "roles",
    nombre: "Roles",
    descripcion: "Roles estándar y propios con sus permisos",
    modulo: "seguridad",
    icono: UserCog,
    tipo: "configuracion",
    area: "seguridad",
    permiso: "seguridad.rol.ver",
    pagina: () => <Roles />,
  },
  {
    ruta: "modulos",
    nombre: "Módulos",
    descripcion: "Activa los módulos que usa la empresa",
    modulo: "seguridad",
    icono: Puzzle,
    tipo: "configuracion",
    area: "seguridad",
    permiso: "seguridad.modulo.ver",
    pagina: () => <Modulos />,
  },
  {
    ruta: "personalizacion",
    nombre: "Personalización",
    descripcion: "Logo y nombre que ven los usuarios",
    modulo: "seguridad",
    icono: Palette,
    tipo: "configuracion",
    area: "seguridad",
    permiso: "seguridad.personalizacion.editar",
    pagina: () => <Personalizacion />,
  },
  {
    ruta: "auditoria",
    nombre: "Auditoría",
    descripcion: "Quién cambió qué y cuándo",
    modulo: "seguridad",
    icono: ScrollText,
    tipo: "configuracion",
    area: "seguridad",
    permiso: "seguridad.auditoria.ver",
    pagina: () => <Auditoria />,
  },
];

/** Pantallas que el usuario puede abrir: módulo activo y alguno de sus permisos. */
export function pantallasVisibles(modulosActivos: Set<string>, puede: (p: string) => boolean): Pantalla[] {
  return PANTALLAS.filter(
    (p) =>
      (Array.isArray(p.modulo) ? p.modulo.some((m) => modulosActivos.has(m)) : modulosActivos.has(p.modulo)) &&
      (!p.permiso || (Array.isArray(p.permiso) ? p.permiso.some(puede) : puede(p.permiso))),
  );
}

export const moduloPrincipal = (p: Pantalla) => (Array.isArray(p.modulo) ? p.modulo[0] : p.modulo);
