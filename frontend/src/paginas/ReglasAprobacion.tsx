import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  api,
  type AprobadorRegla,
  type CatalogoAprobacion,
  type NivelRegla,
  type Opcion,
  type OpcionesEmpresa,
  type ReglaAprobacion,
} from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel, monto } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva } from "../empresa";
import { useSesion } from "../sesion";

type Formulario = {
  nombre: string;
  prioridad: number;
  activo: boolean;
  unidad_negocio_id: string;
  categoria_id: string;
  tipo_articulo: string;
  centro_costo_id: string;
  niveles: NivelRegla[];
};

const aprobadorVacio = (): AprobadorRegla => ({
  tipo: "usuario",
  usuario_id: null,
  rol_id: null,
  unidad_negocio_id: null,
  categoria_id: null,
  centro_costo_id: null,
});
const nivelVacio = (desde = "0"): NivelRegla => ({ monto_desde: desde, modo: "serie", aprobadores: [aprobadorVacio()] });

const MODO_CORTO: Record<string, string> = {
  serie: "En serie",
  paralelo_todos: "Paralelo · todos",
  paralelo_cualquiera: "Paralelo · cualquiera",
};

export default function ReglasAprobacion() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const [documento, setDocumento] = useState("");
  const editar = puede(documento === "orden_compra" ? "compras.regla.editar" : "solicitudes.regla.editar");
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [reglas, setReglas] = useState<ReglaAprobacion[]>([]);
  const [catalogo, setCatalogo] = useState<CatalogoAprobacion | null>(null);
  const [opciones, setOpciones] = useState<OpcionesEmpresa | null>(null);
  const [usuarios, setUsuarios] = useState<Opcion[]>([]);
  const [roles, setRoles] = useState<Opcion[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<ReglaAprobacion | "nueva" | null>(null);
  const [form, setForm] = useState<Formulario | null>(null);
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api<CatalogoAprobacion>("/aprobaciones/catalogo")
      .then((c) => {
        setCatalogo(c);
        setDocumento((d) => d || c.documentos[0]?.codigo || "");
      })
      .catch(setError);
    api<Opcion[]>("/seguridad/opciones/usuarios").then(setUsuarios).catch(() => setUsuarios([]));
    api<Opcion[]>("/seguridad/opciones/roles").then(setRoles).catch(() => setRoles([]));
  }, []);

  const cargar = useCallback(async () => {
    if (!empresa || !documento) return;
    setError(null);
    try {
      const [r, o] = await Promise.all([
        api<ReglaAprobacion[]>(`/aprobaciones/empresas/${empresa.id}/reglas?documento=${documento}`),
        api<OpcionesEmpresa>(`/aprobaciones/empresas/${empresa.id}/opciones`),
      ]);
      setReglas(r);
      setOpciones(o);
    } catch (e) {
      setError(e);
    }
  }, [empresa, documento]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const abrir = (r: ReglaAprobacion | "nueva") => {
    setErrorForm(null);
    setEditando(r);
    setForm(
      r === "nueva"
        ? {
            nombre: "",
            prioridad: (reglas.at(-1)?.prioridad ?? 0) + 1,
            activo: true,
            unidad_negocio_id: "",
            categoria_id: "",
            tipo_articulo: "",
            centro_costo_id: "",
            niveles: [nivelVacio()],
          }
        : {
            nombre: r.nombre,
            prioridad: r.prioridad,
            activo: r.activo,
            unidad_negocio_id: r.unidad_negocio_id ?? "",
            categoria_id: r.categoria_id ?? "",
            tipo_articulo: r.tipo_articulo ?? "",
            centro_costo_id: r.centro_costo_id ?? "",
            niveles: r.niveles.map((n) => ({ ...n, monto_desde: String(Number(n.monto_desde)) })),
          },
    );
  };
  const cerrar = useCallback(() => setEditando(null), []);

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    if (!empresa || !form) return;
    setGuardando(true);
    setErrorForm(null);
    const cuerpo = {
      ...form,
      unidad_negocio_id: form.unidad_negocio_id || null,
      categoria_id: form.categoria_id || null,
      tipo_articulo: form.tipo_articulo || null,
      centro_costo_id: form.centro_costo_id || null,
      niveles: form.niveles.map((n) => ({
        monto_desde: n.monto_desde || "0",
        modo: n.modo,
        aprobadores: n.aprobadores.map((a) => ({
          tipo: a.tipo,
          usuario_id: a.tipo === "usuario" ? a.usuario_id : null,
          rol_id: a.tipo === "rol" ? a.rol_id : null,
          unidad_negocio_id: a.unidad_negocio_id || null,
          categoria_id: a.categoria_id || null,
          centro_costo_id: a.centro_costo_id || null,
        })),
      })),
    };
    try {
      if (editando === "nueva") {
        await api(`/aprobaciones/empresas/${empresa.id}/reglas?documento=${documento}`, { metodo: "POST", cuerpo });
        avisar(`Regla «${form.nombre}» creada.`);
      } else if (editando) {
        await api(`/aprobaciones/reglas/${editando.id}`, { metodo: "PUT", cuerpo });
        avisar(`Regla «${form.nombre}» guardada.`);
      }
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const cambiarNivel = (i: number, cambio: Partial<NivelRegla>) =>
    form && setForm({ ...form, niveles: form.niveles.map((n, j) => (j === i ? { ...n, ...cambio } : n)) });
  const cambiarAprobador = (i: number, k: number, cambio: Partial<AprobadorRegla>) =>
    form &&
    cambiarNivel(i, {
      aprobadores: form.niveles[i].aprobadores.map((a, j) => (j === k ? { ...a, ...cambio } : a)),
    });

  const simbolo = empresa?.moneda_funcional ?? "";
  const maxNiveles = catalogo?.max_niveles ?? 3;

  return (
    <>
      <Encabezado
        titulo="Reglas de aprobación"
        descripcion="Quién aprueba las solicitudes y las órdenes de compra. Se usa la primera regla, por prioridad, cuyas condiciones cumple el documento; cada nivel se activa desde un monto."
        accion={
          editar && (
            <button className="boton boton-primario" onClick={() => abrir("nueva")} disabled={!empresa}>
              Crear regla
            </button>
          )
        }
      />
      <div className="barra-filtros">
        {catalogo && catalogo.documentos.length > 1 && (
          <div className="pestanas" role="tablist">
            {catalogo.documentos.map((d) => (
              <button key={d.codigo} role="tab" aria-selected={documento === d.codigo} onClick={() => setDocumento(d.codigo)}>
                {d.nombre}
              </button>
            ))}
          </div>
        )}
        <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={elegir} />
      </div>
      <MensajeError error={error} />
      {!empresa ? (
        <SinEmpresa cargando={cargando} />
      ) : reglas.length === 0 ? (
        <div className="vacio">
          <p>Aún no hay reglas. Sin una regla, {documento === "orden_compra" ? "las órdenes" : "las solicitudes"} de esta empresa no se pueden enviar a aprobación.</p>
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Prioridad</th>
                <th>Regla</th>
                <th>Se aplica a</th>
                <th>Niveles</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {reglas.map((r) => (
                <tr key={r.id} onClick={() => abrir(r)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrir(r)}>
                  <td className="fuerte">{r.prioridad}</td>
                  <td>{r.nombre}</td>
                  <td>{r.condiciones}</td>
                  <td>
                    <ul className="niveles-resumen">
                      {r.niveles.map((n) => (
                        <li key={n.numero}>
                          <strong>N{n.numero}</strong> desde {monto(n.monto_desde, simbolo)} · {MODO_CORTO[n.modo]}:{" "}
                          {n.aprobadores.map((a) => a.descripcion).join(n.modo === "serie" ? " → " : ", ")}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td>
                    <Estado activo={r.activo} si="Activa" no="Inactiva" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel
        titulo={editando === "nueva" ? "Crear regla de aprobación" : `Regla «${form?.nombre ?? ""}»`}
        abierto={editando !== null && form !== null}
        onCerrar={cerrar}
        ancho
      >
        {form && opciones && catalogo && (
          <form className="formulario" onSubmit={guardar}>
            <div className="fila-formulario">
              <label style={{ flexGrow: 3 }}>
                Nombre
                <input value={form.nombre} maxLength={100} required disabled={!editar} placeholder="General Lima" onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
              </label>
              <label>
                Prioridad
                <input type="number" min={1} value={form.prioridad} required disabled={!editar} onChange={(e) => setForm({ ...form, prioridad: Number(e.target.value) })} />
              </label>
            </div>

            <fieldset>
              <legend>Se aplica a (vacío = todas)</legend>
              <div className="fila-formulario">
                <Selector etiqueta="Unidad de negocio" valor={form.unidad_negocio_id} opciones={opciones.unidades} deshabilitado={!editar} onCambio={(v) => setForm({ ...form, unidad_negocio_id: v })} />
                <Selector etiqueta="Categoría (incluye subcategorías)" valor={form.categoria_id} opciones={opciones.categorias} deshabilitado={!editar} onCambio={(v) => setForm({ ...form, categoria_id: v })} />
              </div>
              <div className="fila-formulario">
                <label>
                  Tipo de artículo
                  <select value={form.tipo_articulo} disabled={!editar} onChange={(e) => setForm({ ...form, tipo_articulo: e.target.value })}>
                    <option value="">Cualquiera</option>
                    {opciones.tipos_articulo.map((t) => (
                      <option key={t.codigo} value={t.codigo}>
                        {t.nombre}
                      </option>
                    ))}
                  </select>
                </label>
                <Selector etiqueta="Centro de costo" valor={form.centro_costo_id} opciones={opciones.centros} deshabilitado={!editar} onCambio={(v) => setForm({ ...form, centro_costo_id: v })} />
              </div>
              <small>Un documento cumple una condición si al menos una de sus líneas la cumple.</small>
            </fieldset>

            {form.niveles.map((n, i) => (
              <section key={i} className="nivel-regla" aria-label={`Nivel ${i + 1}`}>
                <div className="linea-sol-cabecera">
                  <h4>Nivel {i + 1}</h4>
                  {editar && form.niveles.length > 1 && (
                    <button type="button" className="boton boton-chico" onClick={() => setForm({ ...form, niveles: form.niveles.filter((_, j) => j !== i) })}>
                      Quitar nivel
                    </button>
                  )}
                </div>
                <div className="fila-formulario">
                  <label>
                    Se activa desde ({simbolo})
                    <input type="number" min={0} step="0.01" value={n.monto_desde} disabled={!editar} onChange={(e) => cambiarNivel(i, { monto_desde: e.target.value })} />
                  </label>
                  <label>
                    Modo
                    <select value={n.modo} disabled={!editar} onChange={(e) => cambiarNivel(i, { modo: e.target.value })}>
                      {catalogo.modos.map((m) => (
                        <option key={m.codigo} value={m.codigo}>
                          {m.nombre}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {n.aprobadores.map((a, k) => (
                  <div key={k} className="aprobador-regla">
                    <div className="fila-formulario">
                      <label>
                        {n.modo === "serie" ? `Aprobador ${k + 1}` : "Aprobador"}
                        <select value={a.tipo} disabled={!editar} onChange={(e) => cambiarAprobador(i, k, { tipo: e.target.value })}>
                          {catalogo.tipos_aprobador.map((t) => (
                            <option key={t.codigo} value={t.codigo}>
                              {t.nombre}
                            </option>
                          ))}
                        </select>
                      </label>
                      {a.tipo === "usuario" && (
                        <Selector etiqueta="Usuario" valor={a.usuario_id ?? ""} opciones={usuarios} requerido vacio="Elige…" deshabilitado={!editar} onCambio={(v) => cambiarAprobador(i, k, { usuario_id: v })} />
                      )}
                      {a.tipo === "rol" && (
                        <Selector etiqueta="Rol" valor={a.rol_id ?? ""} opciones={roles} requerido vacio="Elige…" deshabilitado={!editar} onCambio={(v) => cambiarAprobador(i, k, { rol_id: v })} />
                      )}
                      {editar && n.aprobadores.length > 1 && (
                        <button type="button" className="boton boton-chico" onClick={() => cambiarNivel(i, { aprobadores: n.aprobadores.filter((_, j) => j !== k) })}>
                          Quitar
                        </button>
                      )}
                    </div>
                    <details open={Boolean(a.unidad_negocio_id || a.categoria_id || a.centro_costo_id)}>
                      <summary className="tenue">Solo si… (opcional)</summary>
                      <div className="fila-formulario">
                        <Selector etiqueta="Unidad" valor={a.unidad_negocio_id ?? ""} opciones={opciones.unidades} deshabilitado={!editar} onCambio={(v) => cambiarAprobador(i, k, { unidad_negocio_id: v })} />
                        <Selector etiqueta="Categoría" valor={a.categoria_id ?? ""} opciones={opciones.categorias} deshabilitado={!editar} onCambio={(v) => cambiarAprobador(i, k, { categoria_id: v })} />
                        <Selector etiqueta="Centro de costo" valor={a.centro_costo_id ?? ""} opciones={opciones.centros} deshabilitado={!editar} onCambio={(v) => cambiarAprobador(i, k, { centro_costo_id: v })} />
                      </div>
                    </details>
                  </div>
                ))}
                {editar && (
                  <div>
                    <button type="button" className="boton boton-chico" onClick={() => cambiarNivel(i, { aprobadores: [...n.aprobadores, aprobadorVacio()] })}>
                      Agregar aprobador
                    </button>
                  </div>
                )}
              </section>
            ))}
            {editar && form.niveles.length < maxNiveles && (
              <div>
                <button
                  type="button"
                  className="boton"
                  onClick={() => setForm({ ...form, niveles: [...form.niveles, nivelVacio(form.niveles.at(-1)?.monto_desde ?? "0")] })}
                >
                  Agregar nivel {form.niveles.length + 1}
                </button>
              </div>
            )}

            <label className="opcion">
              <input type="checkbox" checked={form.activo} disabled={!editar} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
              <span>Regla activa</span>
            </label>
            <MensajeError error={errorForm} />
            {editar && (
              <div className="acciones">
                <button type="button" className="boton" onClick={cerrar}>
                  Cancelar
                </button>
                <BotonAccion ocupado={guardando} textoOcupado={editando === "nueva" ? "Creando…" : "Guardando…"}>
                  {editando === "nueva" ? "Crear regla" : "Guardar cambios"}
                </BotonAccion>
              </div>
            )}
          </form>
        )}
      </Panel>
    </>
  );
}

function Selector({
  etiqueta,
  valor,
  opciones,
  onCambio,
  deshabilitado,
  requerido,
  vacio = "Cualquiera",
}: {
  etiqueta: string;
  valor: string;
  opciones: { id: string; nombre: string; codigo?: string; detalle?: string | null }[];
  onCambio: (v: string) => void;
  deshabilitado?: boolean;
  requerido?: boolean;
  vacio?: string;
}) {
  return (
    <label>
      {etiqueta}
      <select value={valor} required={requerido} disabled={deshabilitado} onChange={(e) => onCambio(e.target.value)}>
        <option value="">{vacio}</option>
        {opciones.map((o) => (
          <option key={o.id} value={o.id}>
            {o.codigo ? `${o.codigo} · ${o.nombre}` : o.nombre}
          </option>
        ))}
      </select>
    </label>
  );
}
