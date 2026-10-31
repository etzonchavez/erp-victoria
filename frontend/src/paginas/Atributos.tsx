import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, NOMBRE_NIVEL, NOMBRE_TIPO_ATRIBUTO, type AtributoConfig, type DocumentoOperativo } from "../api";
import { CamposAtributos, olvidarAtributos, valoresIniciales, type ValoresAtributos } from "../atributos";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { useSesion } from "../sesion";

type Formulario = {
  activo: boolean;
  etiqueta: string;
  ayuda: string;
  valor_defecto: string;
  valores: string;
  copiar: string; // "documento:numero" o ""
};

export default function Atributos() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const editar = puede("seguridad.atributo.editar");
  const [documentos, setDocumentos] = useState<DocumentoOperativo[]>([]);
  const [todos, setTodos] = useState<AtributoConfig[]>([]);
  const [documento, setDocumento] = useState("solicitud");
  const [nivel, setNivel] = useState("cabecera");
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<AtributoConfig | null>(null);
  const [form, setForm] = useState<Formulario>({ activo: true, etiqueta: "", ayuda: "", valor_defecto: "", valores: "", copiar: "" });
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);
  const [vista, setVista] = useState<ValoresAtributos>({});
  const [version, setVersion] = useState(0);

  const cargar = useCallback(async () => {
    try {
      setTodos(await api<AtributoConfig[]>("/seguridad/atributos"));
    } catch (e) {
      setError(e);
    }
  }, []);
  useEffect(() => {
    api<DocumentoOperativo[]>("/seguridad/documentos").then(setDocumentos).catch(setError);
    cargar();
  }, [cargar]);

  const doc = documentos.find((d) => d.codigo === documento);
  const delNivel = todos.filter((a) => a.documento === documento && a.nivel === nivel);
  const activos = delNivel.filter((a) => a.activo);
  const nombreDoc = (codigo: string) => documentos.find((d) => d.codigo === codigo)?.nombre ?? codigo;

  // Valores por defecto en la vista previa al cambiar de documento o nivel
  useEffect(() => setVista(valoresIniciales(activos)), [documento, nivel, version]); // eslint-disable-line react-hooks/exhaustive-deps

  // Destinos posibles para copiar: atributos activos del mismo tipo y nivel en los documentos siguientes
  const destinos = useMemo(() => {
    if (!editando || !doc) return [];
    return todos.filter(
      (a) => doc.destinos.includes(a.documento) && a.nivel === nivel && a.tipo === editando.tipo && a.activo,
    );
  }, [editando, doc, todos, nivel]);

  const abrir = (a: AtributoConfig) => {
    setErrorForm(null);
    setEditando(a);
    setForm({
      activo: a.activo || true,
      etiqueta: a.etiqueta ?? "",
      ayuda: a.ayuda ?? "",
      valor_defecto: a.valor_defecto ?? "",
      valores: a.valores.join("\n"),
      copiar: a.copiar_documento ? `${a.copiar_documento}:${a.copiar_numero}` : "",
    });
  };
  const cerrar = useCallback(() => setEditando(null), []);

  const guardar = async (e: FormEvent, activo = form.activo) => {
    e.preventDefault();
    if (!editando) return;
    setGuardando(true);
    setErrorForm(null);
    const [copiarDoc, copiarNum] = form.copiar ? form.copiar.split(":") : [null, null];
    try {
      await api(`/seguridad/atributos/${documento}/${nivel}/${editando.tipo}/${editando.numero}`, {
        metodo: "PUT",
        cuerpo: {
          activo,
          etiqueta: form.etiqueta,
          ayuda: form.ayuda,
          valor_defecto: form.valor_defecto || null,
          valores: editando.tipo === "texto" ? form.valores.split("\n") : [],
          copiar_documento: copiarDoc,
          copiar_numero: copiarNum ? Number(copiarNum) : null,
        },
      });
      avisar(activo ? `Atributo ${form.etiqueta} guardado.` : `Atributo ${editando.etiqueta} desactivado.`);
      olvidarAtributos();
      setEditando(null);
      await cargar();
      setVersion((v) => v + 1);
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const destinoTexto = (a: AtributoConfig) => {
    if (!a.copiar_documento) return <span className="tenue">—</span>;
    const d = todos.find((x) => x.documento === a.copiar_documento && x.nivel === a.nivel && x.tipo === a.tipo && x.numero === a.copiar_numero);
    return `${nombreDoc(a.copiar_documento)} · ${d?.etiqueta ?? `${NOMBRE_TIPO_ATRIBUTO[a.tipo]} ${a.copiar_numero}`}`;
  };

  return (
    <>
      <Encabezado
        titulo="Atributos adicionales"
        descripcion="Campos propios de tu organización en los documentos de compra: 10 de texto, 10 numéricos y 10 de fecha por nivel. Actívalos, nómbralos y decide si pasan al documento siguiente."
      />
      <div className="barra-filtros">
        <div className="pestanas" role="tablist">
          {documentos.map((d) => (
            <button key={d.codigo} role="tab" aria-selected={d.codigo === documento} onClick={() => setDocumento(d.codigo)}>
              {d.nombre}
            </button>
          ))}
        </div>
        <div className="pestanas pestanas-chicas" role="tablist">
          {(doc?.niveles ?? []).map((n) => (
            <button key={n} role="tab" aria-selected={n === nivel} onClick={() => setNivel(n)}>
              {NOMBRE_NIVEL[n]} ({todos.filter((a) => a.documento === documento && a.nivel === n && a.activo).length})
            </button>
          ))}
        </div>
      </div>
      <MensajeError error={error} />

      <div className="atributos-grid">
        {(["texto", "numero", "fecha"] as const).map((tipo) => (
          <section key={tipo} className="bloque bloque-tabla">
            <h2>{NOMBRE_TIPO_ATRIBUTO[tipo]}</h2>
            <table className="tabla tabla-compacta">
              <tbody>
                {delNivel
                  .filter((a) => a.tipo === tipo)
                  .map((a) => (
                    <tr key={a.columna} onClick={() => editar && abrir(a)} tabIndex={editar ? 0 : undefined} onKeyDown={(k) => k.key === "Enter" && editar && abrir(a)}>
                      <td className="tenue numero">{a.numero}</td>
                      <td>
                        {a.activo ? <span className="fuerte">{a.etiqueta}</span> : <span className="tenue">Disponible</span>}
                        {a.activo && a.valores.length > 0 && <p className="tenue">Lista de {a.valores.length} valores</p>}
                        {a.activo && a.copiar_documento && <p className="tenue">→ {destinoTexto(a)}</p>}
                      </td>
                      <td>{a.activo && <Estado activo />}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </section>
        ))}
      </div>

      <section className="bloque vista-previa">
        <h2>
          Vista previa: {doc?.nombre} · {NOMBRE_NIVEL[nivel]}
        </h2>
        {activos.length === 0 ? (
          <p className="tenue">No hay atributos activos en este nivel. Haz clic en uno disponible para activarlo.</p>
        ) : (
          <CamposAtributos key={`${documento}-${nivel}-${version}`} documento={documento} nivel={nivel} valores={vista} onCambio={setVista} />
        )}
      </section>

      <Panel
        titulo={editando ? `${NOMBRE_TIPO_ATRIBUTO[editando.tipo]} ${editando.numero} · ${doc?.nombre} (${NOMBRE_NIVEL[nivel].toLowerCase()})` : ""}
        abierto={editando !== null}
        onCerrar={cerrar}
      >
        {editando && (
          <form className="formulario" onSubmit={(e) => guardar(e, true)}>
            <label>
              Nombre del campo
              <input value={form.etiqueta} required maxLength={60} placeholder="N.° de proyecto" onChange={(e) => setForm({ ...form, etiqueta: e.target.value })} />
            </label>
            <label>
              <span>
                Texto de ayuda <span className="tenue">(opcional)</span>
              </span>
              <input value={form.ayuda} maxLength={200} onChange={(e) => setForm({ ...form, ayuda: e.target.value })} />
            </label>
            {editando.tipo === "texto" && (
              <label>
                <span>
                  Lista de valores <span className="tenue">(opcional, uno por línea)</span>
                </span>
                <textarea rows={4} value={form.valores} placeholder={"P-100 Planta Lurín\nP-200 Almacén Callao"} onChange={(e) => setForm({ ...form, valores: e.target.value })} />
                <small>Si la llenas, el usuario elige de la lista en vez de escribir.</small>
              </label>
            )}
            <label>
              <span>
                Valor por defecto <span className="tenue">(opcional)</span>
              </span>
              <input
                type={editando.tipo === "numero" ? "number" : editando.tipo === "fecha" ? "date" : "text"}
                step={editando.tipo === "numero" ? "0.0001" : undefined}
                value={form.valor_defecto}
                onChange={(e) => setForm({ ...form, valor_defecto: e.target.value })}
              />
            </label>
            {doc && doc.destinos.length > 0 && (
              <label>
                Copiar al documento siguiente
                <select value={form.copiar} onChange={(e) => setForm({ ...form, copiar: e.target.value })}>
                  <option value="">No copiar</option>
                  {destinos.map((d) => (
                    <option key={`${d.documento}:${d.numero}`} value={`${d.documento}:${d.numero}`}>
                      {nombreDoc(d.documento)} · {d.etiqueta} ({NOMBRE_TIPO_ATRIBUTO[d.tipo]} {d.numero})
                    </option>
                  ))}
                </select>
                <small>
                  {destinos.length === 0
                    ? `Para copiarlo, activa primero un atributo de ${NOMBRE_TIPO_ATRIBUTO[editando.tipo].toLowerCase()} en el nivel ${NOMBRE_NIVEL[nivel].toLowerCase()} de ${doc.destinos.map(nombreDoc).join(", ")}.`
                    : "Al generar el documento siguiente, el valor pasa a ese atributo."}
                </small>
              </label>
            )}
            <MensajeError error={errorForm} />
            <div className="acciones">
              {editando.activo && (
                <button type="button" className="boton" style={{ marginRight: "auto" }} disabled={guardando} onClick={(e) => guardar(e as unknown as FormEvent, false)}>
                  Desactivar
                </button>
              )}
              <button type="button" className="boton" onClick={cerrar}>
                Cancelar
              </button>
              <BotonAccion ocupado={guardando}>{editando.activo ? "Guardar cambios" : "Activar atributo"}</BotonAccion>
            </div>
          </form>
        )}
      </Panel>
    </>
  );
}
