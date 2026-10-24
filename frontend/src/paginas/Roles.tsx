import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, NOMBRE_TIPO, type Modulo, type Permiso, type Rol, type TipoRol } from "../api";
import { Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { useSesion } from "../sesion";

type Formulario = {
  codigo: string;
  modulo: string;
  nombre: string;
  tipo: string;
  descripcion: string;
  activo: boolean;
  permisos: string[];
};
const VACIO: Formulario = {
  codigo: "",
  modulo: "seguridad",
  nombre: "",
  tipo: "operativo",
  descripcion: "",
  activo: true,
  permisos: [],
};

// nuevo: rol propio desde cero · editar: rol propio existente · ver: rol estándar · duplicar: copia de otro rol
type Modo = { tipo: "nuevo" } | { tipo: "editar"; rol: Rol } | { tipo: "ver"; rol: Rol } | { tipo: "duplicar"; rol: Rol };

// Nomenclatura: ERP_<ABREVIATURA DEL MÓDULO>_<FUNCIÓN>, por ejemplo ERP_COM_ANALISTA
const funcion = (texto: string) =>
  texto
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
const aCodigo = (nombre: string, abreviatura: string) => `ERP_${abreviatura}_${funcion(nombre)}`.slice(0, 50);

export default function Roles() {
  const { puede, sesion } = useSesion();
  const [roles, setRoles] = useState<Rol[]>([]);
  const [permisos, setPermisos] = useState<Permiso[]>([]);
  const [tipos, setTipos] = useState<TipoRol[]>([]);
  const [modulos, setModulos] = useState<Modulo[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [modo, setModo] = useState<Modo | null>(null);
  const [form, setForm] = useState<Formulario>(VACIO);
  const [codigoTocado, setCodigoTocado] = useState(false);
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      const [r, p, t] = await Promise.all([
        api<Rol[]>("/seguridad/roles"),
        api<Permiso[]>("/seguridad/permisos"),
        api<TipoRol[]>("/seguridad/tipos-rol"),
      ]);
      setRoles(r);
      setPermisos(p);
      setTipos(t);
      setModulos(puede("seguridad.modulo.ver") ? await api<Modulo[]>("/seguridad/modulos") : (sesion?.modulos ?? []));
    } catch (e) {
      setError(e);
    }
  }, [puede, sesion]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const porModulo = useMemo(() => {
    const grupos = new Map<string, Permiso[]>();
    for (const p of permisos) grupos.set(p.modulo, [...(grupos.get(p.modulo) ?? []), p]);
    return [...grupos.entries()];
  }, [permisos]);
  const nombreModulo = (c: string) => modulos.find((m) => m.codigo === c)?.nombre ?? c;
  const abreviatura = (c: string) => modulos.find((m) => m.codigo === c)?.abreviatura ?? "SEG";
  const descripcionPermiso = (c: string) => permisos.find((p) => p.codigo === c)?.descripcion ?? c;
  const porTipo = tipos.map((t) => ({ ...t, roles: roles.filter((r) => r.tipo === t.codigo) }));

  const abrir = (m: Modo) => {
    setErrorForm(null);
    setModo(m);
    setCodigoTocado(false);
    if (m.tipo === "nuevo") setForm(VACIO);
    else if (m.tipo === "duplicar")
      setForm({
        ...VACIO,
        modulo: m.rol.modulo,
        nombre: `${m.rol.nombre} (copia)`,
        codigo: aCodigo(`${m.rol.nombre} copia`, abreviatura(m.rol.modulo)),
        tipo: m.rol.tipo,
      });
    else
      setForm({
        codigo: m.rol.codigo,
        modulo: m.rol.modulo,
        nombre: m.rol.nombre,
        tipo: m.rol.tipo,
        descripcion: m.rol.descripcion ?? "",
        activo: m.rol.activo,
        permisos: m.rol.permisos,
      });
  };
  const cerrar = useCallback(() => setModo(null), []);

  const cambiarNombre = (nombre: string) =>
    setForm((f) => ({
      ...f,
      nombre,
      codigo: codigoTocado || modo?.tipo === "editar" ? f.codigo : aCodigo(nombre, abreviatura(f.modulo)),
    }));
  const cambiarModulo = (modulo: string) =>
    setForm((f) => {
      // Mantiene la función y cambia solo el prefijo del módulo
      const resto = f.codigo.replace(/^ERP_[A-Z]{3}_/, "") || funcion(f.nombre);
      return { ...f, modulo, codigo: `ERP_${abreviatura(modulo)}_${resto}`.slice(0, 50) };
    });

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    if (!modo) return;
    setGuardando(true);
    setErrorForm(null);
    const descripcion = form.descripcion.trim() || null;
    try {
      if (modo.tipo === "nuevo") {
        await api("/seguridad/roles", { metodo: "POST", cuerpo: { ...form, descripcion } });
      } else if (modo.tipo === "duplicar") {
        await api(`/seguridad/roles/${modo.rol.id}/duplicar`, {
          metodo: "POST",
          cuerpo: { codigo: form.codigo, nombre: form.nombre, modulo: form.modulo },
        });
      } else if (modo.tipo === "editar") {
        await api(`/seguridad/roles/${modo.rol.id}`, {
          metodo: "PATCH",
          cuerpo: { nombre: form.nombre, tipo: form.tipo, descripcion, activo: form.activo, permisos: form.permisos },
        });
      }
      setModo(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

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

  const titulo =
    modo?.tipo === "nuevo"
      ? "Crear rol"
      : modo?.tipo === "duplicar"
        ? `Duplicar ${modo.rol.nombre}`
        : modo?.tipo === "ver"
          ? modo.rol.nombre
          : "Editar rol";

  return (
    <>
      <Encabezado
        titulo="Roles"
        descripcion="Los roles estándar vienen con el ERP y se actualizan con cada versión. Para adaptarlos a tu empresa, duplícalos."
        accion={
          puede("seguridad.rol.crear") && (
            <button className="boton boton-primario" onClick={() => abrir({ tipo: "nuevo" })}>
              Crear rol
            </button>
          )
        }
      />
      <MensajeError error={error} />
      <div className="tabla-contenedor">
        <table className="tabla">
          <thead>
            <tr>
              <th>Rol</th>
              <th>Módulo</th>
              <th>Descripción</th>
              <th className="numero">Permisos</th>
              <th>Estado</th>
            </tr>
          </thead>
          {porTipo.map((t) => (
            <tbody key={t.codigo}>
              <tr className="fila-grupo">
                <th colSpan={5} scope="rowgroup">
                  {NOMBRE_TIPO[t.codigo] ?? t.codigo}
                  <span>{t.descripcion}</span>
                </th>
              </tr>
              {t.roles.map((r) => (
                <tr
                  key={r.id}
                  tabIndex={0}
                  onClick={() => abrir(r.estandar ? { tipo: "ver", rol: r } : { tipo: "editar", rol: r })}
                  onKeyDown={(e) => e.key === "Enter" && abrir(r.estandar ? { tipo: "ver", rol: r } : { tipo: "editar", rol: r })}
                >
                  <td>
                    <span className="fuerte">{r.nombre}</span>
                    {r.estandar && <span className="etiqueta etiqueta-estandar">Estándar</span>}
                    <br />
                    <code>{r.codigo}</code>
                  </td>
                  <td>{nombreModulo(r.modulo)}</td>
                  <td className="tenue">{r.descripcion}</td>
                  <td className="numero">{r.permisos.length}</td>
                  <td>
                    <Estado activo={r.activo} />
                  </td>
                </tr>
              ))}
              {t.roles.length === 0 && (
                <tr>
                  <td colSpan={5} className="tenue">
                    Sin roles de este tipo.
                  </td>
                </tr>
              )}
            </tbody>
          ))}
        </table>
      </div>

      <Panel titulo={titulo} abierto={modo !== null} onCerrar={cerrar}>
        {modo?.tipo === "ver" ? (
          <div className="formulario">
            <p className="aviso aviso-info">
              Rol estándar de tipo {NOMBRE_TIPO[modo.rol.tipo]?.toLowerCase()}. No se puede modificar; duplícalo para crear una versión
              propia que sí puedas ajustar.
            </p>
            {modo.rol.descripcion && <p>{modo.rol.descripcion}</p>}
            <div>
              <p className="fuerte">Permisos</p>
              <ul className="lista-permisos">
                {modo.rol.permisos.map((p) => (
                  <li key={p}>
                    {descripcionPermiso(p)} <code>{p}</code>
                  </li>
                ))}
              </ul>
            </div>
            <div className="acciones">
              <button type="button" className="boton" onClick={cerrar}>
                Cerrar
              </button>
              {puede("seguridad.rol.crear") && (
                <button className="boton boton-primario" onClick={() => abrir({ tipo: "duplicar", rol: modo.rol })}>
                  Duplicar rol
                </button>
              )}
            </div>
          </div>
        ) : (
          <form className="formulario" onSubmit={guardar}>
            {modo?.tipo === "duplicar" && (
              <p className="aviso aviso-info">
                El rol nuevo copia el tipo y los {modo.rol.permisos.length} permisos de {modo.rol.nombre}. Después podrás ajustarlos.
              </p>
            )}
            <label>
              Módulo
              <select value={form.modulo} disabled={modo?.tipo === "editar"} onChange={(e) => cambiarModulo(e.target.value)}>
                {modulos.map((m) => (
                  <option key={m.codigo} value={m.codigo}>
                    {m.nombre} ({m.abreviatura})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Nombre
              <input value={form.nombre} onChange={(e) => cambiarNombre(e.target.value)} required />
            </label>
            <label>
              Código
              <input
                value={form.codigo}
                disabled={modo?.tipo === "editar"}
                onChange={(e) => {
                  setCodigoTocado(true);
                  setForm({ ...form, codigo: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_") });
                }}
                required
              />
              <small>
                Formato ERP_{abreviatura(form.modulo)}_FUNCIÓN, por ejemplo ERP_{abreviatura(form.modulo)}_ANALISTA. Se genera
                desde el nombre y no se puede cambiar después.
              </small>
            </label>

            {modo?.tipo !== "duplicar" && (
              <>
                <fieldset>
                  <legend>Tipo de rol</legend>
                  {tipos.map((t) => (
                    <label key={t.codigo} className="opcion">
                      <input
                        type="radio"
                        name="tipo"
                        checked={form.tipo === t.codigo}
                        onChange={() => setForm({ ...form, tipo: t.codigo })}
                      />
                      <span>
                        {NOMBRE_TIPO[t.codigo] ?? t.codigo}
                        <small>{t.descripcion}</small>
                      </span>
                    </label>
                  ))}
                </fieldset>
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
                        <button type="button" className="enlace" onClick={() => alternarGrupo(lista, marcados < lista.length)}>
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

                {modo?.tipo === "editar" && (
                  <label className="opcion">
                    <input type="checkbox" checked={form.activo} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
                    <span>
                      Rol activo
                      <small>Si lo desactivas, sus usuarios pierden estos permisos de inmediato.</small>
                    </span>
                  </label>
                )}
              </>
            )}

            <MensajeError error={errorForm} />
            <div className="acciones">
              <button type="button" className="boton" onClick={cerrar}>
                Cancelar
              </button>
              {(modo?.tipo === "editar" ? puede("seguridad.rol.editar") : puede("seguridad.rol.crear")) && (
                <button className="boton boton-primario" disabled={guardando}>
                  {guardando
                    ? "Guardando…"
                    : modo?.tipo === "duplicar"
                      ? "Crear copia"
                      : modo?.tipo === "nuevo"
                        ? "Crear rol"
                        : "Guardar cambios"}
                </button>
              )}
            </div>
          </form>
        )}
      </Panel>
    </>
  );
}
