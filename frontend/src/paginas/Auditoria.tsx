import { useEffect, useState } from "react";
import { api, type EventoAuditoria } from "../api";
import { Encabezado, MensajeError, fecha } from "../componentes";

const VERBOS: Record<string, string> = {
  crear: "Creó",
  editar: "Editó",
  activar: "Activó",
  desactivar: "Desactivó",
};
const SINGULAR: Record<string, string> = { usuario: "el usuario", rol: "el rol", modulo: "el módulo" };
const ENTIDADES: Record<string, string> = { usuario: "Usuarios", rol: "Roles", modulo: "Módulos", sesion: "Ingresos" };
const CAMPOS: Record<string, string> = {
  email: "Correo",
  nombre: "Nombre",
  codigo: "Código",
  activo: "Activo",
  es_administrador: "Administrador",
  roles: "Roles",
  permisos: "Permisos",
  descripcion: "Descripción",
  password: "Contraseña",
  origen: "Origen",
};

function accion(e: EventoAuditoria): string {
  if (e.accion === "login") return "Ingresó al ERP";
  if (e.accion === "login_fallido") return "Intento de ingreso fallido";
  const objeto = SINGULAR[e.entidad] ?? e.entidad;
  const nombre = e.entidad === "modulo" ? ` ${e.entidad_id}` : "";
  return `${VERBOS[e.accion] ?? e.accion} ${objeto}${nombre}`;
}

function resumen(e: EventoAuditoria): string {
  const d = e.detalle;
  if (!d) return "";
  return Object.entries(d)
    .map(([campo, valor]) => {
      const etiqueta = CAMPOS[campo] ?? campo;
      if (valor && typeof valor === "object" && "antes" in valor && "despues" in valor) {
        const v = valor as { antes: unknown; despues: unknown };
        return `${etiqueta}: ${texto(v.antes)} → ${texto(v.despues)}`;
      }
      return `${etiqueta}: ${texto(valor)}`;
    })
    .join("; ");
}
const texto = (v: unknown) =>
  Array.isArray(v) ? (v.length ? v.join(", ") : "ninguno") : typeof v === "boolean" ? (v ? "sí" : "no") : String(v);

export default function Auditoria() {
  const [eventos, setEventos] = useState<EventoAuditoria[]>([]);
  const [entidad, setEntidad] = useState("");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const q = new URLSearchParams({ limite: "200", ...(entidad ? { entidad } : {}) });
    api<EventoAuditoria[]>(`/seguridad/auditoria?${q}`)
      .then(setEventos)
      .catch(setError);
  }, [entidad]);

  return (
    <>
      <Encabezado
        titulo="Auditoría"
        descripcion="Registro de quién hizo qué y cuándo. No se puede editar ni borrar."
        accion={
          <label className="filtro">
            Mostrar
            <select value={entidad} onChange={(e) => setEntidad(e.target.value)}>
              <option value="">Todo</option>
              {Object.entries(ENTIDADES).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
        }
      />
      <MensajeError error={error} />
      <div className="tabla-contenedor">
        <table className="tabla tabla-auditoria">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Usuario</th>
              <th>Acción</th>
              <th>Detalle</th>
            </tr>
          </thead>
          <tbody>
            {eventos.map((e) => (
              <tr key={e.id} className={e.accion === "login_fallido" ? "fila-alerta" : undefined}>
                <td className="numero">{fecha(e.fecha)}</td>
                <td>{e.usuario_email ?? <span className="tenue">Sistema</span>}</td>
                <td>{accion(e)}</td>
                <td className="detalle">{resumen(e)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
