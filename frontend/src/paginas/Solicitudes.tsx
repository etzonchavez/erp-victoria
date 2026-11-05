import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  api,
  type ArticuloOpcion,
  type CatalogoAprobacion,
  type OpcionesEmpresa,
  type PasoAprobacion,
  type RutaAprobacion,
  type Solicitud,
  type SolicitudResumen,
} from "../api";
import { CamposAtributos, useAtributos, valoresIniciales, type ValoresAtributos } from "../atributos";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, MensajeError, Panel, fecha, fechaDia, monto } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva, type EmpresaResumen } from "../empresa";
import { useSesion } from "../sesion";

const DOC = "solicitud";
type Alcance = "por_aprobar" | "mias" | "todas";
type Vista = { modo: "nueva" } | { modo: "ver"; id: string } | { modo: "editar"; sol: Solicitud } | null;

const NOMBRE_ESTADO: Record<string, string> = {
  borrador: "Borrador",
  en_aprobacion: "En aprobación",
  devuelta: "Devuelta",
  rechazada: "Rechazada",
  aprobada: "Aprobada",
  atendida: "Atendida",
  anulada: "Anulada",
};
const NOMBRE_PASO: Record<string, string> = {
  en_espera: "En espera",
  pendiente: "Pendiente",
  aprobado: "Aprobó",
  rechazado: "Rechazó",
  devuelto: "Devolvió",
  omitido: "Omitido",
  cancelado: "No fue necesario",
};
const MODO: Record<string, string> = {
  serie: "en serie",
  paralelo_todos: "en paralelo · todos",
  paralelo_cualquiera: "en paralelo · basta uno",
};

export function EstadoSolicitud({ estado }: { estado: string }) {
  return <span className={`etiqueta etiqueta-sol sol-${estado}`}>{NOMBRE_ESTADO[estado] ?? estado}</span>;
}

export { BuscadorArticulo, HistorialRonda, NOMBRE_ESTADO, NOMBRE_PASO };

export default function Solicitudes() {
  const { puede } = useSesion();
  const crear = puede("solicitudes.solicitud.crear");
  const verTodas = puede("solicitudes.solicitud.ver");
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [alcance, setAlcance] = useState<Alcance>(crear ? "mias" : "por_aprobar");
  const [estado, setEstado] = useState("");
  const [lista, setLista] = useState<SolicitudResumen[]>([]);
  const [porAprobar, setPorAprobar] = useState<SolicitudResumen[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [vista, setVista] = useState<Vista>(null);

  const cargar = useCallback(async () => {
    setError(null);
    try {
      const bandeja = await api<SolicitudResumen[]>("/solicitudes/bandeja");
      setPorAprobar(bandeja);
      if (alcance === "por_aprobar") setLista(bandeja.filter((s) => !estado || s.estado === estado));
      else if (empresa) {
        const q = new URLSearchParams({ empresa_id: empresa.id, alcance });
        if (estado) q.set("estado", estado);
        setLista(await api<SolicitudResumen[]>(`/solicitudes?${q}`));
      }
    } catch (e) {
      setError(e);
    }
  }, [alcance, estado, empresa]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const cerrar = useCallback(() => setVista(null), []);
  const pestanas: { codigo: Alcance; nombre: string; visible: boolean }[] = [
    { codigo: "por_aprobar", nombre: "Por aprobar", visible: true },
    { codigo: "mias", nombre: "Mis solicitudes", visible: crear },
    { codigo: "todas", nombre: "Todas", visible: verTodas },
  ];

  return (
    <>
      <Encabezado
        titulo="Solicitudes de compra"
        descripcion="Pide lo que necesitas comprar. Al enviarla, la solicitud pasa por los aprobadores que define la regla de su empresa."
        accion={
          crear && (
            <button className="boton boton-primario" onClick={() => setVista({ modo: "nueva" })} disabled={!empresa}>
              Nueva solicitud
            </button>
          )
        }
      />
      <div className="barra-filtros">
        <div className="pestanas" role="tablist">
          {pestanas
            .filter((p) => p.visible)
            .map((p) => (
              <button key={p.codigo} role="tab" aria-selected={alcance === p.codigo} onClick={() => setAlcance(p.codigo)}>
                {p.nombre}
                {p.codigo === "por_aprobar" && porAprobar.length > 0 && <span className="contador">{porAprobar.length}</span>}
              </button>
            ))}
        </div>
        {alcance !== "por_aprobar" && <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={elegir} />}
        <label className="filtro">
          Estado
          <select value={estado} onChange={(e) => setEstado(e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(NOMBRE_ESTADO).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      </div>
      <MensajeError error={error} />
      {alcance !== "por_aprobar" && !empresa ? (
        <SinEmpresa cargando={cargando} />
      ) : lista.length === 0 ? (
        <div className="vacio">
          <p>
            {alcance === "por_aprobar"
              ? "No tienes solicitudes esperando tu aprobación."
              : alcance === "mias"
                ? "Aún no registras solicitudes en esta empresa."
                : "No hay solicitudes con este filtro."}
          </p>
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Número</th>
                <th>Título</th>
                <th>Unidad</th>
                <th>Solicitante</th>
                <th className="numero">Total</th>
                <th>Estado</th>
                <th>Pendiente de</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((s) => (
                <tr key={s.id} onClick={() => setVista({ modo: "ver", id: s.id })} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && setVista({ modo: "ver", id: s.id })}>
                  <td className="fuerte sin-corte">{s.numero}</td>
                  <td>{s.titulo}</td>
                  <td>{s.unidad_negocio}</td>
                  <td>{s.solicitante}</td>
                  <td className="numero sin-corte">{monto(s.total, s.moneda)}</td>
                  <td>
                    <EstadoSolicitud estado={s.estado} />
                  </td>
                  <td>{s.pendiente_de.join(", ") || <span className="tenue">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel
        titulo={
          vista?.modo === "nueva" ? "Nueva solicitud" : vista?.modo === "editar" ? `Editar ${vista.sol.numero}` : "Solicitud de compra"
        }
        abierto={vista !== null}
        onCerrar={cerrar}
        ancho
      >
        {vista?.modo === "ver" && (
          <DetalleSolicitud
            id={vista.id}
            onEditar={(sol) => setVista({ modo: "editar", sol })}
            onCambio={cargar}
          />
        )}
        {(vista?.modo === "nueva" || vista?.modo === "editar") && empresa && (
          <FormSolicitud
            empresa={vista.modo === "editar" ? (empresas.find((e) => e.id === vista.sol.empresa_id) ?? empresa) : empresa}
            inicial={vista.modo === "editar" ? vista.sol : null}
            onCancelar={() => (vista.modo === "editar" ? setVista({ modo: "ver", id: vista.sol.id }) : cerrar())}
            onGuardado={(sol) => {
              setVista({ modo: "ver", id: sol.id });
              cargar();
            }}
          />
        )}
      </Panel>
    </>
  );
}

// ---------------------------------------------------------------- formulario

type ArticuloLinea = Pick<ArticuloOpcion, "id" | "codigo" | "descripcion" | "unidad" | "unidades" | "precio_referencial" | "moneda_precio">;
type RepartoForm = { centro_costo_id: string; porcentaje: string; atributos: ValoresAtributos };
type LineaForm = {
  clave: number;
  articulo: ArticuloLinea | null;
  descripcion: string;
  cantidad: string;
  unidad: string;
  precio: string;
  atributos: ValoresAtributos;
  distribuciones: RepartoForm[];
};
type CabeceraForm = {
  unidad_negocio_id: string;
  titulo: string;
  justificacion: string;
  fecha_requerida: string;
  moneda: string;
  atributos: ValoresAtributos;
};

const texto = (v: ValoresAtributos | Record<string, string | null>): ValoresAtributos =>
  Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x == null ? "" : String(x)]));

let siguienteClave = 1;

function FormSolicitud({
  empresa,
  inicial,
  onCancelar,
  onGuardado,
}: {
  empresa: EmpresaResumen;
  inicial: Solicitud | null;
  onCancelar: () => void;
  onGuardado: (s: Solicitud) => void;
}) {
  const { avisar } = useAvisos();
  const [opciones, setOpciones] = useState<OpcionesEmpresa | null>(null);
  const atrCabecera = useAtributos(DOC, "cabecera");
  const atrLinea = useAtributos(DOC, "linea");
  const atrReparto = useAtributos(DOC, "distribucion");
  const [cab, setCab] = useState<CabeceraForm>(() => ({
    unidad_negocio_id: inicial?.unidad_negocio_id ?? "",
    titulo: inicial?.titulo ?? "",
    justificacion: inicial?.justificacion ?? "",
    fecha_requerida: inicial?.fecha_requerida ?? "",
    moneda: inicial?.moneda ?? empresa.moneda_funcional,
    atributos: inicial ? texto(inicial.atributos) : {},
  }));
  const [lineas, setLineas] = useState<LineaForm[]>(() =>
    inicial
      ? inicial.lineas.map((l) => ({
          clave: siguienteClave++,
          articulo: {
            id: l.articulo_id,
            codigo: l.articulo,
            descripcion: l.descripcion,
            unidad: l.unidad_base,
            unidades: l.unidad !== l.unidad_base ? [{ unidad: l.unidad, factor: "" }] : [],
            precio_referencial: null,
            moneda_precio: null,
          },
          descripcion: l.descripcion,
          cantidad: String(Number(l.cantidad)),
          unidad: l.unidad,
          precio: String(Number(l.precio)),
          atributos: texto(l.atributos),
          distribuciones: l.distribuciones.map((d) => ({
            centro_costo_id: d.centro_costo_id,
            porcentaje: String(Number(d.porcentaje)),
            atributos: texto(d.atributos),
          })),
        }))
      : [],
  );
  const [error, setError] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api<OpcionesEmpresa>(`/solicitudes/empresas/${empresa.id}/opciones`)
      .then((o) => {
        setOpciones(o);
        setCab((c) => (c.unidad_negocio_id ? c : { ...c, unidad_negocio_id: o.unidades[0]?.id ?? "" }));
      })
      .catch(setError);
  }, [empresa.id]);

  // Valores por defecto de los atributos en una solicitud nueva
  useEffect(() => {
    if (!inicial && atrCabecera.length) setCab((c) => ({ ...c, atributos: { ...valoresIniciales(atrCabecera), ...c.atributos } }));
  }, [atrCabecera, inicial]);

  const repartoNuevo = (): RepartoForm => ({
    centro_costo_id: opciones?.centros[0]?.id ?? "",
    porcentaje: "100",
    atributos: valoresIniciales(atrReparto),
  });
  const agregarLinea = () =>
    setLineas((ls) => [
      ...ls,
      {
        clave: siguienteClave++,
        articulo: null,
        descripcion: "",
        cantidad: "1",
        unidad: "",
        precio: "0",
        atributos: valoresIniciales(atrLinea),
        distribuciones: [repartoNuevo()],
      },
    ]);
  const cambiarLinea = (clave: number, cambio: Partial<LineaForm>) =>
    setLineas((ls) => ls.map((l) => (l.clave === clave ? { ...l, ...cambio } : l)));

  const total = lineas.reduce((s, l) => s + (Number(l.cantidad) || 0) * (Number(l.precio) || 0), 0);

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setGuardando(true);
    const cuerpo = {
      unidad_negocio_id: cab.unidad_negocio_id,
      titulo: cab.titulo,
      justificacion: cab.justificacion || null,
      fecha_requerida: cab.fecha_requerida || null,
      moneda: cab.moneda,
      atributos: cab.atributos,
      lineas: lineas.map((l) => ({
        articulo_id: l.articulo?.id,
        descripcion: l.descripcion || null,
        cantidad: l.cantidad,
        unidad: l.unidad || null,
        precio: l.precio || "0",
        atributos: l.atributos,
        distribuciones: l.distribuciones.map((d) => ({ ...d })),
      })),
    };
    try {
      if (lineas.some((l) => !l.articulo)) throw new Error("Elige el artículo de cada línea");
      const sol = inicial
        ? await api<Solicitud>(`/solicitudes/${inicial.id}`, { metodo: "PUT", cuerpo })
        : await api<Solicitud>("/solicitudes", { metodo: "POST", cuerpo: { ...cuerpo, empresa_id: empresa.id } });
      avisar(inicial ? `Solicitud ${sol.numero} guardada.` : `Solicitud ${sol.numero} registrada como borrador.`);
      onGuardado(sol);
    } catch (err) {
      setError(err);
    } finally {
      setGuardando(false);
    }
  };

  if (!opciones) return <MensajeError error={error} />;
  const monedas = Array.from(new Set([empresa.moneda_funcional, "USD", cab.moneda]));

  return (
    <form className="formulario" onSubmit={guardar}>
      <div className="fila-formulario">
        <label style={{ flexGrow: 3 }}>
          Título
          <input value={cab.titulo} maxLength={150} required placeholder="Útiles de oficina para el área de ventas" onChange={(e) => setCab({ ...cab, titulo: e.target.value })} />
        </label>
        <label>
          Unidad de negocio
          <select value={cab.unidad_negocio_id} required onChange={(e) => setCab({ ...cab, unidad_negocio_id: e.target.value })}>
            {opciones.unidades.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nombre}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="fila-formulario">
        <label>
          <span>
            Fecha requerida <span className="tenue">(opcional)</span>
          </span>
          <input type="date" value={cab.fecha_requerida} onChange={(e) => setCab({ ...cab, fecha_requerida: e.target.value })} />
        </label>
        <label>
          Moneda
          <select value={cab.moneda} onChange={(e) => setCab({ ...cab, moneda: e.target.value })}>
            {monedas.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label>
        <span>
          Justificación <span className="tenue">(opcional)</span>
        </span>
        <textarea rows={2} maxLength={2000} value={cab.justificacion} onChange={(e) => setCab({ ...cab, justificacion: e.target.value })} />
      </label>
      <CamposAtributos documento={DOC} nivel="cabecera" valores={cab.atributos} onCambio={(v) => setCab({ ...cab, atributos: v })} />

      <div className="subseccion">
        <h3>Líneas</h3>
        {lineas.length === 0 && <p className="tenue">Agrega lo que necesitas comprar.</p>}
        {lineas.map((l, i) => {
          const subtotal = (Number(l.cantidad) || 0) * (Number(l.precio) || 0);
          const suma = l.distribuciones.reduce((s, d) => s + (Number(d.porcentaje) || 0), 0);
          const unidades = l.articulo ? [l.articulo.unidad, ...l.articulo.unidades.map((u) => u.unidad)] : [];
          return (
            <section key={l.clave} className="linea-sol" aria-label={`Línea ${i + 1}`}>
              <div className="linea-sol-cabecera">
                <h4>Línea {i + 1}</h4>
                <button type="button" className="boton boton-chico" onClick={() => setLineas(lineas.filter((x) => x.clave !== l.clave))}>
                  Quitar línea
                </button>
              </div>
              <BuscadorArticulo
                articulo={l.articulo}
                onElegir={(a) =>
                  cambiarLinea(l.clave, {
                    articulo: a,
                    descripcion: a.descripcion,
                    unidad: a.unidad,
                    precio: a.precio_referencial && a.moneda_precio === cab.moneda ? String(Number(a.precio_referencial)) : l.precio,
                  })
                }
              />
              <div className="fila-formulario">
                <label style={{ flexGrow: 3 }}>
                  Descripción
                  <input value={l.descripcion} maxLength={240} onChange={(e) => cambiarLinea(l.clave, { descripcion: e.target.value })} />
                </label>
                <label>
                  Cantidad
                  <input type="number" min="0" step="0.0001" required value={l.cantidad} onChange={(e) => cambiarLinea(l.clave, { cantidad: e.target.value })} />
                </label>
                <label>
                  Unidad
                  <select value={l.unidad} onChange={(e) => cambiarLinea(l.clave, { unidad: e.target.value })} disabled={!l.articulo}>
                    {unidades.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Precio estimado ({cab.moneda})
                  <input type="number" min="0" step="0.0001" value={l.precio} onChange={(e) => cambiarLinea(l.clave, { precio: e.target.value })} />
                </label>
                <p className="numero sin-corte" style={{ alignSelf: "center" }}>
                  {monto(subtotal, cab.moneda)}
                </p>
              </div>
              <CamposAtributos documento={DOC} nivel="linea" valores={l.atributos} onCambio={(v) => cambiarLinea(l.clave, { atributos: v })} />
              <div className="reparto">
                <small>
                  Centros de costo {suma !== 100 && <span className="texto-alerta">· los porcentajes suman {suma}, deben sumar 100</span>}
                </small>
                {l.distribuciones.map((d, k) => {
                  const cambiar = (c: Partial<RepartoForm>) =>
                    cambiarLinea(l.clave, { distribuciones: l.distribuciones.map((x, j) => (j === k ? { ...x, ...c } : x)) });
                  return (
                    <div key={k}>
                      <div className="fila-formulario">
                        <label>
                          Centro de costo
                          <select value={d.centro_costo_id} required onChange={(e) => cambiar({ centro_costo_id: e.target.value })}>
                            <option value="">Elige…</option>
                            {opciones.centros.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.codigo} · {c.nombre}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="porcentaje">
                          %
                          <input type="number" min="0.0001" max="100" step="0.0001" required value={d.porcentaje} onChange={(e) => cambiar({ porcentaje: e.target.value })} />
                        </label>
                        {l.distribuciones.length > 1 && (
                          <button type="button" className="boton boton-chico" onClick={() => cambiarLinea(l.clave, { distribuciones: l.distribuciones.filter((_, j) => j !== k) })}>
                            Quitar
                          </button>
                        )}
                      </div>
                      <CamposAtributos documento={DOC} nivel="distribucion" valores={d.atributos} onCambio={(v) => cambiar({ atributos: v })} />
                    </div>
                  );
                })}
                <div>
                  <button
                    type="button"
                    className="boton boton-chico"
                    onClick={() =>
                      cambiarLinea(l.clave, {
                        distribuciones: [...l.distribuciones, { ...repartoNuevo(), centro_costo_id: "", porcentaje: String(Math.max(0, 100 - suma)) }],
                      })
                    }
                  >
                    Repartir con otro centro
                  </button>
                </div>
              </div>
            </section>
          );
        })}
        <div>
          <button type="button" className="boton" onClick={agregarLinea}>
            Agregar línea
          </button>
        </div>
        <p className="total-sol">
          Total estimado <strong>{monto(total, cab.moneda)}</strong>
        </p>
      </div>

      <MensajeError error={error} />
      <div className="acciones">
        <button type="button" className="boton" onClick={onCancelar}>
          Cancelar
        </button>
        <BotonAccion ocupado={guardando} disabled={lineas.length === 0}>
          {inicial ? "Guardar cambios" : "Guardar borrador"}
        </BotonAccion>
      </div>
    </form>
  );
}

function BuscadorArticulo({
  articulo,
  onElegir,
  ruta = "/solicitudes/articulos",
}: {
  articulo: ArticuloLinea | null;
  onElegir: (a: ArticuloOpcion) => void;
  ruta?: string;
}) {
  const [buscando, setBuscando] = useState(!articulo);
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState<ArticuloOpcion[]>([]);
  const temporizador = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!buscando) return;
    window.clearTimeout(temporizador.current);
    temporizador.current = window.setTimeout(() => {
      api<ArticuloOpcion[]>(`${ruta}?texto=${encodeURIComponent(q)}`)
        .then(setResultados)
        .catch(() => setResultados([]));
    }, 250);
    return () => window.clearTimeout(temporizador.current);
  }, [q, buscando, ruta]);

  if (!buscando && articulo)
    return (
      <p className="fila-formulario" style={{ alignItems: "center" }}>
        <span>
          <span className="fuerte">{articulo.codigo}</span> · {articulo.descripcion}
        </span>
        <button type="button" className="boton boton-chico" onClick={() => setBuscando(true)}>
          Cambiar artículo
        </button>
      </p>
    );
  return (
    <div className="buscador-articulo">
      <label>
        Artículo
        <input value={q} autoFocus placeholder="Busca por código, descripción, marca o modelo" onChange={(e) => setQ(e.target.value)} />
      </label>
      <ul className="lista-simple" role="listbox" aria-label="Artículos encontrados">
        {resultados.slice(0, 8).map((a) => (
          <li key={a.id}>
            <button
              type="button"
              className="enlace"
              role="option"
              aria-selected={false}
              onClick={() => {
                onElegir(a);
                setBuscando(false);
              }}
            >
              <span className="fuerte">{a.codigo}</span> · {a.descripcion} <span className="tenue">({a.unidad})</span>
            </button>
          </li>
        ))}
        {resultados.length === 0 && <li className="tenue">Sin resultados.</li>}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- detalle y aprobación

function DetalleSolicitud({ id, onEditar, onCambio }: { id: string; onEditar: (s: Solicitud) => void; onCambio: () => void }) {
  const { avisar } = useAvisos();
  const [sol, setSol] = useState<Solicitud | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [ruta, setRuta] = useState<RutaAprobacion | null>(null);
  const [errorRuta, setErrorRuta] = useState<unknown>(null);
  const [comentario, setComentario] = useState("");
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [anulando, setAnulando] = useState(false);
  const [catalogo, setCatalogo] = useState<CatalogoAprobacion | null>(null);

  const cargar = useCallback(async () => {
    try {
      setSol(await api<Solicitud>(`/solicitudes/${id}`));
    } catch (e) {
      setError(e);
    }
  }, [id]);
  useEffect(() => {
    cargar();
    api<CatalogoAprobacion>("/aprobaciones/catalogo").then(setCatalogo).catch(() => null);
  }, [cargar]);

  // Antes de enviar, se muestra quién aprobaría
  useEffect(() => {
    if (!sol || !sol.acciones.enviar) return;
    setErrorRuta(null);
    api<RutaAprobacion>(`/solicitudes/${sol.id}/ruta`)
      .then(setRuta)
      .catch((e) => {
        setRuta(null);
        setErrorRuta(e);
      });
  }, [sol]);

  if (!sol) return <MensajeError error={error} />;

  const ejecutar = async (accion: string, mensaje: string, cuerpo?: unknown) => {
    setOcupado(accion);
    setError(null);
    try {
      const nueva = await api<Solicitud>(`/solicitudes/${sol.id}/${accion}`, { metodo: "POST", cuerpo: cuerpo ?? {} });
      setSol(nueva);
      setComentario("");
      setAnulando(false);
      avisar(`${mensaje} ${nueva.numero}: ${NOMBRE_ESTADO[nueva.estado].toLowerCase()}.`);
      onCambio();
    } catch (e) {
      setError(e);
    } finally {
      setOcupado(null);
    }
  };

  const rondas = Array.from(new Set(sol.pasos.map((p) => p.ronda))).sort((a, b) => b - a);
  const nombreModo = (m: string) => catalogo?.modos.find((x) => x.codigo === m)?.nombre ?? MODO[m];

  return (
    <div className="formulario">
      <div className="linea-sol-cabecera">
        <div>
          <h3 style={{ margin: 0 }}>
            {sol.numero} · {sol.titulo}
          </h3>
          <p className="tenue">
            {sol.solicitante} · {sol.unidad_negocio} · {fechaDia(sol.fecha)}
            {sol.fecha_requerida && ` · se necesita el ${fechaDia(sol.fecha_requerida)}`}
          </p>
        </div>
        <EstadoSolicitud estado={sol.estado} />
      </div>
      {sol.orden_compra_numero && <p className="aviso aviso-info">Atendida en la orden de compra {sol.orden_compra_numero}.</p>}
      {sol.justificacion && <p>{sol.justificacion}</p>}

      <div className="tabla-contenedor">
        <table className="tabla tabla-compacta">
          <thead>
            <tr>
              <th>#</th>
              <th>Artículo</th>
              <th className="numero">Cantidad</th>
              <th className="numero">Precio</th>
              <th className="numero">Subtotal</th>
              <th>Centro de costo</th>
              <th>Cuenta</th>
            </tr>
          </thead>
          <tbody>
            {sol.lineas.map((l) => (
              <tr key={l.numero}>
                <td>{l.numero}</td>
                <td>
                  <span className="fuerte">{l.articulo}</span> {l.descripcion}
                </td>
                <td className="numero sin-corte">
                  {Number(l.cantidad)} {l.unidad}
                </td>
                <td className="numero">{monto(l.precio)}</td>
                <td className="numero">{monto(l.subtotal)}</td>
                <td>{l.distribuciones.map((d) => `${d.centro_costo} ${Number(d.porcentaje)}%`).join(" · ")}</td>
                <td>{l.cuenta ?? <span className="tenue">Al enviar</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="total-sol">
        Total <strong>{monto(sol.total, sol.moneda)}</strong>
        {Number(sol.tipo_cambio) !== 1 && Number(sol.total_funcional) > 0 && (
          <span className="tenue">≈ {monto(sol.total_funcional)} (T.C. {Number(sol.tipo_cambio)})</span>
        )}
      </p>

      {sol.acciones.aprobar && (
        <div className="decision">
          <strong>Tienes esta solicitud pendiente de aprobación</strong>
          <label>
            Comentario <span className="tenue">(obligatorio para devolver o rechazar)</span>
            <textarea rows={2} maxLength={500} value={comentario} onChange={(e) => setComentario(e.target.value)} />
          </label>
          <div className="acciones-linea">
            <BotonAccion ocupado={ocupado === "aprobar"} textoOcupado="Aprobando…" onClick={() => ejecutar("aprobar", "Aprobaste la solicitud", { comentario })}>
              Aprobar
            </BotonAccion>
            <BotonAccion primario={false} ocupado={ocupado === "devolver"} textoOcupado="Devolviendo…" onClick={() => ejecutar("devolver", "Devolviste la solicitud", { comentario })}>
              Devolver para corregir
            </BotonAccion>
            <BotonAccion primario={false} className="boton-peligro" ocupado={ocupado === "rechazar"} textoOcupado="Rechazando…" onClick={() => ejecutar("rechazar", "Rechazaste la solicitud", { comentario })}>
              Rechazar
            </BotonAccion>
          </div>
        </div>
      )}

      <MensajeError error={error} />

      {sol.acciones.enviar && (
        <div className="subseccion">
          <h3>Quién aprobará</h3>
          {errorRuta ? (
            <MensajeError error={errorRuta} />
          ) : ruta ? (
            ruta.niveles.length === 0 ? (
              <p>Según la regla «{ruta.regla}», por su monto esta solicitud se aprueba al enviarla.</p>
            ) : (
              <>
                <p className="tenue">Regla «{ruta.regla}»</p>
                <ol className="ruta">
                  {ruta.niveles.map((n) => (
                    <li key={n.numero} className="ruta-nivel">
                      <header>
                        <strong>Nivel {n.numero}</strong>
                        <span>{nombreModo(n.modo)}</span>
                      </header>
                      {n.pasos.map((p, k) => (
                        <div key={k} className={`paso paso-${p.estado === "omitido" ? "omitido" : "en_espera"}`}>
                          <div>
                            {p.descripcion}
                            {p.motivo && <p>{p.motivo}: se omite</p>}
                          </div>
                        </div>
                      ))}
                    </li>
                  ))}
                </ol>
              </>
            )
          ) : (
            <p className="tenue">Calculando…</p>
          )}
        </div>
      )}

      {rondas.length > 0 && (
        <div className="subseccion">
          <h3>Aprobación</h3>
          {rondas.map((r) => (
            <HistorialRonda key={r} ronda={r} pasos={sol.pasos.filter((p) => p.ronda === r)} actual={r === sol.ronda} nombreModo={nombreModo} />
          ))}
        </div>
      )}

      {anulando && (
        <div className="decision">
          <label>
            Motivo de la anulación
            <textarea rows={2} maxLength={500} value={comentario} onChange={(e) => setComentario(e.target.value)} />
          </label>
          <div className="acciones-linea">
            <button type="button" className="boton" onClick={() => setAnulando(false)}>
              No anular
            </button>
            <BotonAccion className="boton-peligro" ocupado={ocupado === "anular"} textoOcupado="Anulando…" onClick={() => ejecutar("anular", "Anulaste la solicitud", { comentario })}>
              Anular solicitud
            </BotonAccion>
          </div>
        </div>
      )}

      <div className="acciones">
        {sol.acciones.anular && !anulando && (
          <button type="button" className="boton" onClick={() => setAnulando(true)}>
            Anular
          </button>
        )}
        {sol.acciones.editar && (
          <button type="button" className="boton" onClick={() => onEditar(sol)}>
            Editar
          </button>
        )}
        {sol.acciones.enviar && (
          <BotonAccion ocupado={ocupado === "enviar"} textoOcupado="Enviando…" disabled={Boolean(errorRuta)} onClick={() => ejecutar("enviar", "Enviaste la solicitud")}>
            {sol.estado === "devuelta" ? "Reenviar a aprobación" : "Enviar a aprobación"}
          </BotonAccion>
        )}
      </div>
    </div>
  );
}

function HistorialRonda({
  ronda,
  pasos,
  actual,
  nombreModo,
}: {
  ronda: number;
  pasos: PasoAprobacion[];
  actual: boolean;
  nombreModo: (m: string) => string;
}) {
  const niveles = Array.from(new Set(pasos.map((p) => p.nivel)));
  const contenido = (
    <ol className="ruta">
      {niveles.map((n) => {
        const del = pasos.filter((p) => p.nivel === n);
        return (
          <li key={n} className="ruta-nivel">
            <header>
              <strong>Nivel {n}</strong>
              <span>{nombreModo(del[0].modo)}</span>
            </header>
            {del.map((p) => (
              <div key={`${p.nivel}-${p.orden}`} className={`paso paso-${p.estado}`}>
                <div>
                  {p.descripcion}
                  {p.actuado_por_nombre && p.actuado_por_nombre !== p.descripcion.split(" · ")[0] && <p>Actuó {p.actuado_por_nombre}</p>}
                  {p.comentario && <p>«{p.comentario}»</p>}
                  {p.motivo && <p>{p.motivo}</p>}
                </div>
                <span className="paso-estado">
                  {NOMBRE_PASO[p.estado] ?? p.estado}
                  {p.actuado_en && <small> · {fecha(p.actuado_en)}</small>}
                </span>
              </div>
            ))}
          </li>
        );
      })}
    </ol>
  );
  if (actual)
    return (
      <>
        {ronda > 1 && <p className="tenue">Envío {ronda} · regla «{pasos[0]?.regla_nombre}»</p>}
        {ronda === 1 && <p className="tenue">Regla «{pasos[0]?.regla_nombre}»</p>}
        {contenido}
      </>
    );
  return (
    <details>
      <summary className="tenue">Envío {ronda} (anterior)</summary>
      {contenido}
    </details>
  );
}
