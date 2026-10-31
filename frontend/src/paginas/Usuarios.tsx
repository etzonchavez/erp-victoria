import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, NOMBRE_TIPO, type Rol, type Usuario } from "../api";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel, fecha } from "../componentes";
import { useAvisos } from "../avisos";
import { useSesion } from "../sesion";
import { AccesosUsuario } from "../accesos";

type Formulario = {
  email: string;
  nombre: string;
  password: string;
  activo: boolean;
  es_administrador: boolean;
  roles: string[];
};

const VACIO: Formulario = { email: "", nombre: "", password: "", activo: true, es_administrador: false, roles: [] };

export default function Usuarios() {
  const { sesion, puede, recargar } = useSesion();
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [roles, setRoles] = useState<Rol[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<Usuario | "nuevo" | null>(null);
  const [form, setForm] = useState<Formulario>(VACIO);
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);
  const [empresasPorUsuario, setEmpresasPorUsuario] = useState<Record<string, number> | null>(null);
  const { avisar } = useAvisos();

  const cargar = useCallback(async () => {
    try {
      setUsuarios(await api<Usuario[]>("/seguridad/usuarios"));
      api<Record<string, number>>("/maestros/accesos/resumen")
        .then(setEmpresasPorUsuario)
        .catch(() => setEmpresasPorUsuario(null));
      if (puede("seguridad.rol.ver")) setRoles(await api<Rol[]>("/seguridad/roles"));
    } catch (e) {
      setError(e);
    }
  }, [puede]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const abrir = (u: Usuario | "nuevo") => {
    setErrorForm(null);
    setEditando(u);
    setForm(
      u === "nuevo"
        ? VACIO
        : {
            email: u.email,
            nombre: u.nombre,
            password: "",
            activo: u.activo,
            es_administrador: u.es_administrador,
            roles: u.roles.map((r) => r.id),
          },
    );
  };
  const cerrar = useCallback(() => setEditando(null), []);

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setGuardando(true);
    setErrorForm(null);
    try {
      if (editando === "nuevo") {
        await api("/seguridad/usuarios", { metodo: "POST", cuerpo: form });
      } else if (editando) {
        const cambios: Partial<Formulario> = { nombre: form.nombre, activo: form.activo, roles: form.roles };
        if (form.password) cambios.password = form.password;
        if (sesion?.usuario.es_administrador) cambios.es_administrador = form.es_administrador;
        await api(`/seguridad/usuarios/${editando.id}`, { metodo: "PATCH", cuerpo: cambios });
        if (editando.id === sesion?.usuario.id) await recargar();
      }
      avisar(editando === "nuevo" ? `Usuario ${form.email} creado.` : `Cambios de ${form.nombre} guardados.`);
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const nuevo = editando === "nuevo";
  const puedeGuardar = nuevo ? puede("seguridad.usuario.crear") : puede("seguridad.usuario.editar");
  const alternarRol = (id: string) =>
    setForm((f) => ({ ...f, roles: f.roles.includes(id) ? f.roles.filter((r) => r !== id) : [...f.roles, id] }));

  return (
    <>
      <Encabezado
        titulo="Usuarios"
        descripcion="Personas que ingresan al ERP y los roles que definen lo que pueden hacer."
        accion={
          puede("seguridad.usuario.crear") && (
            <button className="boton boton-primario" onClick={() => abrir("nuevo")}>
              Crear usuario
            </button>
          )
        }
      />
      <MensajeError error={error} />
      <div className="tabla-contenedor">
        <table className="tabla">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Correo</th>
              <th>Roles</th>
              <th>Último acceso</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {usuarios.map((u) => (
              <tr key={u.id} onClick={() => abrir(u)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && abrir(u)}>
                <td className="fuerte">{u.nombre}</td>
                <td>{u.email}</td>
                <td>
                  {u.es_administrador && <span className="etiqueta etiqueta-admin">Administrador</span>}
                  {u.roles.map((r) => (
                    <span key={r.id} className="etiqueta">
                      {r.nombre}
                    </span>
                  ))}
                  {!u.es_administrador && u.roles.length === 0 && <span className="tenue">Sin roles</span>}
                  {!u.es_administrador && empresasPorUsuario && !empresasPorUsuario[u.id] && (
                    <span className="etiqueta etiqueta-alerta">Sin empresas</span>
                  )}
                </td>
                <td className="numero">{fecha(u.ultimo_acceso)}</td>
                <td>
                  <Estado activo={u.activo} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Panel titulo={nuevo ? "Crear usuario" : "Editar usuario"} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          <label>
            Correo
            <input
              type="email"
              value={form.email}
              disabled={!nuevo}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </label>
          <label>
            Nombre completo
            <input value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} required />
          </label>
          <label>
            {nuevo ? "Contraseña" : "Nueva contraseña"}
            <input
              type="password"
              autoComplete="new-password"
              value={form.password}
              placeholder={nuevo ? "Mínimo 8 caracteres" : "Déjala vacía para no cambiarla"}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required={nuevo}
            />
          </label>

          {roles.length > 0 && (
            <fieldset>
              <legend>Roles</legend>
              {roles
                .filter((r) => r.activo || form.roles.includes(r.id))
                .map((r) => (
                  <label key={r.id} className="opcion">
                    <input type="checkbox" checked={form.roles.includes(r.id)} onChange={() => alternarRol(r.id)} />
                    <span>
                      {r.nombre}
                      {!r.activo && <span className="tenue"> (inactivo)</span>}
                      <small>
                        {NOMBRE_TIPO[r.tipo] ?? r.tipo}
                        {r.estandar ? " · estándar" : ""}
                      </small>
                    </span>
                  </label>
                ))}
            </fieldset>
          )}

          {sesion?.usuario.es_administrador && (
            <label className="opcion">
              <input
                type="checkbox"
                checked={form.es_administrador}
                onChange={(e) => setForm({ ...form, es_administrador: e.target.checked })}
              />
              <span>
                Administrador
                <small>Tiene todos los permisos de los módulos activos.</small>
              </span>
            </label>
          )}
          {!nuevo && (
            <label className="opcion">
              <input type="checkbox" checked={form.activo} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
              <span>
                Usuario activo
                <small>Un usuario inactivo no puede ingresar.</small>
              </span>
            </label>
          )}

          <MensajeError error={errorForm} />
          <div className="acciones">
            <button type="button" className="boton" onClick={cerrar}>
              Cancelar
            </button>
            {puedeGuardar && (
              <BotonAccion ocupado={guardando} textoOcupado={nuevo ? "Creando…" : "Guardando…"}>
                {nuevo ? "Crear usuario" : "Guardar cambios"}
              </BotonAccion>
            )}
          </div>
        </form>
        {editando && editando !== "nuevo" && (
          <AccesosUsuario usuario={editando} editar={puede("seguridad.usuario.editar")} onCambio={cargar} />
        )}
      </Panel>
    </>
  );
}
