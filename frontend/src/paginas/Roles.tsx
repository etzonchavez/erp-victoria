import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, type Modulo, type Permiso, type Rol } from "../api";
import { Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { useSesion } from "../sesion";

type Formulario = { codigo: string; nombre: string; descripcion: string; activo: boolean; permisos: string[] };
const VACIO: Formulario = { codigo: "", nombre: "", descripcion: "", activo: true, permisos: [] };

export default function Roles() {
  const { puede } = useSesion();
  const [roles, setRoles] = useState<Rol[]>([]);
  const [permisos, setPermisos] = useState<Permiso[]>([]);
  const [modulos, setModulos] = useState<Modulo[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<Rol | "nuevo" | null>(null);
  const [form, setForm] = useState<Formulario>(VACIO);
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const [r, p] = await Promise.all([api<Rol[]>("/seguridad/roles"), api<Permiso[]>("/seguridad/permisos")]);
      setRoles(r);
      setPermisos(p);
      if (puede("seguridad.modulo.ver")) setModulos(await api<Modulo[]>("/seguridad/modulos"));
    } catch (e) {
      setError(e);
    }
  }, [puede]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const porModulo = useMemo(() => {
    const grupos = new Map<string, Permiso[]>();
    for (const p of permisos) grupos.set(p.modulo, [...(grupos.get(p.modulo) ?? []), p]);
    return [...grupos.entries()];
  }, [permisos]);
  const nombreModulo = (c: string) => modulos.find((m) => m.codigo === c)?.nombre ?? c;

  const abrir = (r: Rol | "nuevo") => {
    setErrorForm(null);
    setEditando(r);
    setForm(
      r === "nuevo"
        ? VACIO
        : { codigo: r.codigo, nombre: r.nombre, descripcion: r.descripcion ?? "", activo: r.activo, permisos: r.permisos },
    );
  };
  const cerrar = useCallback(() => setEditando(null), []);

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setGuardando(true);
    setErrorForm(null);
    const descripcion = form.descripcion.trim() || null;
    try {
      if (editando === "nuevo") {
        await api("/seguridad/roles", { metodo: "POST", cuerpo: { ...form, descripcion } });
      } else if (editando) {
        await api(`/seguridad/roles/${editando.id}`, {
          metodo: "PATCH",
          cuerpo: { nombre: form.nombre, descripcion, activo: form.activo, permisos: form.permisos },
        });
      }
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const nuevo = editando === "nuevo";
  const puedeGuardar = nuevo ? puede("seguridad.rol.crear") : puede("seguridad.rol.editar");
  const alternar = (codigo: string) =>
    setForm((f) => ({
      ...f,
      permisos: f.permisos.includes(codigo) ? f.permisos.filter((p) => p !== codigo) : [...f.permisos, codigo],
    }));
  const alternarGrupo = (lista: Permiso[], marcar: boolean) =>
    setForm((f) => {
      const codigos = lista.map((p) => p.codigo);
      const resto = f.permisos.filter((p) => !codigos.includes(p));
      return { ...f, permisos: marcar ? [...resto, ...codigos] : resto };
    });

  return (
    <>
      <Encabezado
        titulo="Roles"
        descripcion="Cada rol agrupa los permisos de un puesto de trabajo, por ejemplo Comprador o Aprobador."
        accion={
          puede("seguridad.rol.crear") && (
            <button className="boton boton-primario" onClick={() => abrir("nuevo")}>
              Crear rol
            </button>
          )
        }
      />
      <MensajeError error={error} />
      {roles.length === 0 && !error ? (
        <div className="vacio">
          <p>Aún no hay roles. Crea el primero para asignar permisos a tus usuarios sin hacerlos administradores.</p>
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Rol</th>
                <th>Código</th>
                <th>Descripción</th>
                <th className="numero">Permisos</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((r) => (
                <tr key={r.id} onClick={() => abrir(r)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && abrir(r)}>
                  <td className="fuerte">{r.nombre}</td>
                  <td>
                    <code>{r.codigo}</code>
                  </td>
                  <td className="tenue">{r.descripcion}</td>
                  <td className="numero">{r.permisos.length}</td>
                  <td>
                    <Estado activo={r.activo} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel titulo={nuevo ? "Crear rol" : "Editar rol"} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          <label>
            Nombre
            <input value={form.nombre} onChange={(e) => setForm({ ...form, nombre: e.target.value })} required />
          </label>
          <label>
            Código
            <input
              value={form.codigo}
              disabled={!nuevo}
              placeholder="comprador"
              onChange={(e) => setForm({ ...form, codigo: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "_") })}
              required
            />
            <small>Minúsculas, números y guion bajo. No se puede cambiar después.</small>
          </label>
          <label>
            Descripción
            <textarea rows={2} value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} />
          </label>

          {porModulo.map(([modulo, lista]) => {
            const marcados = lista.filter((p) => form.permisos.includes(p.codigo)).length;
            return (
              <fieldset key={modulo}>
                <legend>
                  {nombreModulo(modulo)}
                  <button
                    type="button"
                    className="enlace"
                    onClick={() => alternarGrupo(lista, marcados < lista.length)}
                  >
                    {marcados < lista.length ? "Marcar todos" : "Quitar todos"}
                  </button>
                </legend>
                {lista.map((p) => (
                  <label key={p.codigo} className="opcion">
                    <input type="checkbox" checked={form.permisos.includes(p.codigo)} onChange={() => alternar(p.codigo)} />
                    <span>
                      {p.descripcion}
                      <small>
                        <code>{p.codigo}</code>
                      </small>
                    </span>
                  </label>
                ))}
              </fieldset>
            );
          })}

          {!nuevo && (
            <label className="opcion">
              <input type="checkbox" checked={form.activo} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
              <span>
                Rol activo
                <small>Si lo desactivas, sus usuarios pierden estos permisos de inmediato.</small>
              </span>
            </label>
          )}

          <MensajeError error={errorForm} />
          <div className="acciones">
            <button type="button" className="boton" onClick={cerrar}>
              Cancelar
            </button>
            {puedeGuardar && (
              <button className="boton boton-primario" disabled={guardando}>
                {guardando ? "Guardando…" : nuevo ? "Crear rol" : "Guardar cambios"}
              </button>
            )}
          </div>
        </form>
      </Panel>
    </>
  );
}
