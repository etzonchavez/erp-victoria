import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  api,
  archivoUrl,
  type ArticuloOpcion,
  type CatalogoAprobacion,
  type OpcionesCompra,
  type Orden,
  type OrdenResumen,
  type RutaAprobacion,
  type SolicitudDisponible,
} from "../api";
import { CamposAtributos, useAtributos, valoresIniciales, type ValoresAtributos } from "../atributos";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, MensajeError, Panel, parametroRuta, fechaDia, monto } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva, type EmpresaResumen } from "../empresa";
import { useSesion } from "../sesion";
import { BuscadorArticulo, HistorialRonda } from "./Solicitudes";

const DOC = "orden_compra";
type Alcance = "por_aprobar" | "mias" | "todas";
type Vista = { modo: "nueva" } | { modo: "ver"; id: string } | { modo: "editar"; orden: Orden } | null;

const ESTADOS: Record<string, string> = {
  borrador: "Borrador",
  en_aprobacion: "En aprobación",
  devuelta: "Devuelta",
  rechazada: "Rechazada",
  aprobada: "Aprobada",
  enviada: "Enviada al proveedor",
  anulada: "Anulada",
};

function EstadoOrden({ estado }: { estado: string }) {
  return <span className={`etiqueta etiqueta-sol sol-${estado}`}>{ESTADOS[estado] ?? estado}</span>;
}

async function abrirPdf(id: string) {
  const url = await archivoUrl(`/compras/ordenes/${id}/pdf`);
  window.open(url, "_blank", "noopener");
}

export default function OrdenesCompra() {
  const { puede } = useSesion();
  const crear = puede("compras.orden.crear");
  const verTodas = puede("compras.orden.ver");
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [alcance, setAlcance] = useState<Alcance>(() => (parametroRuta("vista") === "por_aprobar" || !crear ? "por_aprobar" : "mias"));
  const [estado, setEstado] = useState("");
  const [lista, setLista] = useState<OrdenResumen[]>([]);
  const [porAprobar, setPorAprobar] = useState<OrdenResumen[]>([]);
  const [error, setError] = useState<unknown>(null);
  // Enlace directo (notificaciones): #/ordenes-compra?id=<documento>
  const [vista, setVista] = useState<Vista>(() => {
    const id = parametroRuta("id");
    return id ? { modo: "ver", id } : null;
  });

  const cargar = useCallback(async () => {
    setError(null);
    try {
      const bandeja = await api<OrdenResumen[]>("/compras/bandeja");
      setPorAprobar(bandeja);
      if (alcance === "por_aprobar") setLista(bandeja.filter((o) => !estado || o.estado === estado));
      else if (empresa) {
        const q = new URLSearchParams({ empresa_id: empresa.id, alcance });
        if (estado) q.set("estado", estado);
        setLista(await api<OrdenResumen[]>(`/compras/ordenes?${q}`));
      }
    } catch (e) {
      setError(e);
    }
  }, [alcance, estado, empresa]);
  useEffect(() => {
    cargar();
  }, [cargar]);
  const cerrar = useCallback(() => {
    setVista(null);
    // Quita ?id= del enlace directo sin recargar la pantalla
    if (parametroRuta("id")) window.history.replaceState(null, "", "#/ordenes-compra");
  }, []);

  const pestanas: { codigo: Alcance; nombre: string; visible: boolean }[] = [
    { codigo: "por_aprobar", nombre: "Por aprobar", visible: true },
    { codigo: "mias", nombre: "Mis órdenes", visible: crear },
    { codigo: "todas", nombre: "Todas", visible: verTodas },
  ];

  return (
    <>
      <Encabezado
        titulo="Órdenes de compra"
        descripcion="Emite órdenes desde solicitudes aprobadas o directas. Pasan por la aprobación configurada y, aprobadas, se envían al proveedor en PDF."
        accion={
          crear && (
            <button className="boton boton-primario" onClick={() => setVista({ modo: "nueva" })} disabled={!empresa}>
              Nueva orden
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
            {Object.entries(ESTADOS).map(([k, v]) => (
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
              ? "No tienes órdenes esperando tu aprobación."
              : alcance === "mias"
                ? "Aún no emites órdenes en esta empresa."
                : "No hay órdenes con este filtro."}
          </p>
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Número</th>
                <th>Proveedor</th>
                <th>Solicitudes</th>
                <th>Comprador</th>
                <th className="numero">Total</th>
                <th>Estado</th>
                <th>Pendiente de</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((o) => (
                <tr key={o.id} onClick={() => setVista({ modo: "ver", id: o.id })} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && setVista({ modo: "ver", id: o.id })}>
                  <td className="fuerte sin-corte">{o.numero}</td>
                  <td>{o.proveedor}</td>
                  <td>{o.solicitudes.join(", ") || <span className="tenue">Directa</span>}</td>
                  <td>{o.comprador}</td>
                  <td className="numero sin-corte">{monto(o.total, o.moneda)}</td>
                  <td>
                    <EstadoOrden estado={o.estado} />
                  </td>
                  <td>{o.pendiente_de.join(", ") || <span className="tenue">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel
        titulo={vista?.modo === "nueva" ? "Nueva orden de compra" : vista?.modo === "editar" ? `Editar ${vista.orden.numero}` : "Orden de compra"}
        abierto={vista !== null}
        onCerrar={cerrar}
        ancho
      >
        {vista?.modo === "ver" && <DetalleOrden id={vista.id} onEditar={(o) => setVista({ modo: "editar", orden: o })} onCambio={cargar} />}
        {(vista?.modo === "nueva" || vista?.modo === "editar") && empresa && (
          <FormOrden
            empresa={vista.modo === "editar" ? (empresas.find((e) => e.id === vista.orden.empresa_id) ?? empresa) : empresa}
            inicial={vista.modo === "editar" ? vista.orden : null}
            onCancelar={() => (vista.modo === "editar" ? setVista({ modo: "ver", id: vista.orden.id }) : cerrar())}
            onGuardado={(o) => {
              setVista({ modo: "ver", id: o.id });
              cargar();
            }}
          />
        )}
      </Panel>
    </>
  );
}

// ---------------------------------------------------------------- formulario

type LineaSol = { id: string; articulo: string; descripcion: string; cantidad: string; unidad: string; precio: string; impuesto_id: string; centros: string };
type SolIncluida = { id: string; numero: string; titulo: string; moneda: string; lineas: LineaSol[] };
type ArticuloLinea = Pick<ArticuloOpcion, "id" | "codigo" | "descripcion" | "unidad" | "unidades" | "precio_referencial" | "moneda_precio">;
type Reparto = { centro_costo_id: string; porcentaje: string; atributos: ValoresAtributos };
type Directa = {
  clave: number;
  articulo: ArticuloLinea | null;
  descripcion: string;
  cantidad: string;
  unidad: string;
  precio: string;
  impuesto_id: string;
  atributos: ValoresAtributos;
  distribuciones: Reparto[];
};
type Cabecera = {
  unidad_negocio_id: string;
  proveedor_id: string;
  contacto_id: string;
  condicion_pago_id: string;
  moneda: string;
  fecha_entrega: string;
  lugar_entrega: string;
  observaciones: string;
  atributos: ValoresAtributos;
};

const texto = (v: Record<string, string | null>): ValoresAtributos =>
  Object.fromEntries(Object.entries(v).map(([k, x]) => [k, x == null ? "" : String(x)]));
let clave = 1;

function FormOrden({
  empresa,
  inicial,
  onCancelar,
  onGuardado,
}: {
  empresa: EmpresaResumen;
  inicial: Orden | null;
  onCancelar: () => void;
  onGuardado: (o: Orden) => void;
}) {
  const { avisar } = useAvisos();
  const atrCabecera = useAtributos(DOC, "cabecera");
  const atrLinea = useAtributos(DOC, "linea");
  const atrReparto = useAtributos(DOC, "distribucion");
  const [op, setOp] = useState<OpcionesCompra | null>(null);
  const [disponibles, setDisponibles] = useState<SolicitudDisponible[]>([]);
  const [cab, setCab] = useState<Cabecera>(() => ({
    unidad_negocio_id: inicial?.unidad_negocio_id ?? "",
    proveedor_id: inicial?.proveedor_id ?? "",
    contacto_id: inicial?.contacto_id ?? "",
    condicion_pago_id: inicial?.condicion_pago_id ?? "",
    moneda: inicial?.moneda ?? empresa.moneda_funcional,
    fecha_entrega: inicial?.fecha_entrega ?? "",
    lugar_entrega: inicial?.lugar_entrega ?? "",
    observaciones: inicial?.observaciones ?? "",
    atributos: inicial ? texto(inicial.atributos) : {},
  }));
  // Solicitudes incluidas (las de una orden en edición ya no figuran como disponibles)
  const [incluidas, setIncluidas] = useState<SolIncluida[]>(() => {
    if (!inicial) return [];
    const grupos = new Map<string, SolIncluida>();
    for (const l of inicial.lineas.filter((x) => x.solicitud_id)) {
      const g = grupos.get(l.solicitud_id!) ?? { id: l.solicitud_id!, numero: l.solicitud_numero ?? "", titulo: "", moneda: inicial.moneda, lineas: [] };
      g.lineas.push({
        id: l.solicitud_linea_id!,
        articulo: l.articulo,
        descripcion: l.descripcion,
        cantidad: l.cantidad,
        unidad: l.unidad,
        precio: String(Number(l.precio)),
        impuesto_id: l.impuesto_id ?? "",
        centros: l.distribuciones.map((d) => d.centro_costo).join(", "),
      });
      grupos.set(g.id, g);
    }
    return Array.from(grupos.values());
  });
  const [directas, setDirectas] = useState<Directa[]>(() =>
    inicial
      ? inicial.lineas
          .filter((l) => !l.solicitud_id)
          .map((l) => ({
            clave: clave++,
            articulo: { id: l.articulo_id, codigo: l.articulo, descripcion: l.descripcion, unidad: l.unidad_base, unidades: l.unidades.slice(1).map((u) => ({ unidad: u, factor: "" })), precio_referencial: null, moneda_precio: null },
            descripcion: l.descripcion,
            cantidad: String(Number(l.cantidad)),
            unidad: l.unidad,
            precio: String(Number(l.precio)),
            impuesto_id: l.impuesto_id ?? "",
            atributos: texto(l.atributos),
            distribuciones: l.distribuciones.map((d) => ({ centro_costo_id: d.centro_costo_id, porcentaje: String(Number(d.porcentaje)), atributos: texto(d.atributos) })),
          }))
      : [],
  );
  const [error, setError] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    Promise.all([
      api<OpcionesCompra>(`/compras/empresas/${empresa.id}/opciones`),
      api<SolicitudDisponible[]>(`/compras/empresas/${empresa.id}/solicitudes-disponibles`),
    ])
      .then(([o, d]) => {
        setOp(o);
        setDisponibles(d);
        setCab((c) => (c.unidad_negocio_id ? c : { ...c, unidad_negocio_id: o.unidades[0]?.id ?? "" }));
      })
      .catch(setError);
  }, [empresa.id]);
  useEffect(() => {
    if (!inicial && atrCabecera.length) setCab((c) => ({ ...c, atributos: { ...valoresIniciales(atrCabecera), ...c.atributos } }));
  }, [atrCabecera, inicial]);

  if (!op) return <MensajeError error={error} />;
  const tasa = (id: string) => Number(op.impuestos.find((i) => i.id === id)?.tasa ?? 0);
  const proveedor = op.proveedores.find((p) => p.id === cab.proveedor_id);
  const elegirProveedor = (id: string) => {
    const p = op.proveedores.find((x) => x.id === id);
    setCab({ ...cab, proveedor_id: id, contacto_id: "", moneda: p?.moneda ?? cab.moneda, condicion_pago_id: p?.condicion_pago_id ?? cab.condicion_pago_id });
  };
  const incluir = (s: SolicitudDisponible, si: boolean) =>
    setIncluidas((xs) =>
      si
        ? [
            ...xs,
            {
              id: s.id,
              numero: s.numero,
              titulo: s.titulo,
              moneda: s.moneda,
              lineas: s.lineas.map((l) => ({
                id: l.id,
                articulo: l.articulo,
                descripcion: l.descripcion,
                cantidad: l.cantidad,
                unidad: l.unidad,
                precio: s.moneda === cab.moneda ? String(Number(l.precio)) : "0",
                impuesto_id: op.impuesto_defecto ?? "",
                centros: l.centros,
              })),
            },
          ]
        : xs.filter((x) => x.id !== s.id),
    );
  const cambiarLineaSol = (solId: string, lineaId: string, cambio: Partial<LineaSol>) =>
    setIncluidas((xs) => xs.map((s) => (s.id !== solId ? s : { ...s, lineas: s.lineas.map((l) => (l.id === lineaId ? { ...l, ...cambio } : l)) })));
  const cambiarDirecta = (k: number, cambio: Partial<Directa>) => setDirectas((ds) => ds.map((d) => (d.clave === k ? { ...d, ...cambio } : d)));

  const lineasCalculo = [
    ...incluidas.flatMap((s) => s.lineas.map((l) => ({ sub: Number(l.cantidad) * Number(l.precio || 0), tasa: tasa(l.impuesto_id) }))),
    ...directas.map((d) => ({ sub: Number(d.cantidad || 0) * Number(d.precio || 0), tasa: tasa(d.impuesto_id) })),
  ];
  const subtotal = lineasCalculo.reduce((a, l) => a + l.sub, 0);
  const impuesto = lineasCalculo.reduce((a, l) => a + Math.round(l.sub * l.tasa) / 100, 0);
  const listaSolicitudes: SolicitudDisponible[] = [
    ...incluidas.filter((i) => !disponibles.some((d) => d.id === i.id)).map((i) => ({ id: i.id, numero: i.numero, titulo: i.titulo, solicitante: "", unidad_negocio: "", fecha_requerida: null, moneda: i.moneda, total: "0", lineas: [] })),
    ...disponibles,
  ];

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setGuardando(true);
    try {
      if (directas.some((d) => !d.articulo)) throw new Error("Elige el artículo de cada línea directa");
      const cuerpo = {
        unidad_negocio_id: cab.unidad_negocio_id,
        proveedor_id: cab.proveedor_id,
        contacto_id: cab.contacto_id || null,
        condicion_pago_id: cab.condicion_pago_id || null,
        moneda: cab.moneda,
        fecha_entrega: cab.fecha_entrega || null,
        lugar_entrega: cab.lugar_entrega || null,
        observaciones: cab.observaciones || null,
        atributos: cab.atributos,
        solicitudes: incluidas.map((s) => s.id),
        lineas: [
          ...incluidas.flatMap((s) => s.lineas.map((l) => ({ solicitud_linea_id: l.id, precio: l.precio || "0", impuesto_id: l.impuesto_id || null }))),
          ...directas.map((d) => ({
            articulo_id: d.articulo?.id,
            descripcion: d.descripcion || null,
            cantidad: d.cantidad,
            unidad: d.unidad || null,
            precio: d.precio || "0",
            impuesto_id: d.impuesto_id || null,
            atributos: d.atributos,
            distribuciones: d.distribuciones,
          })),
        ],
      };
      const o = inicial
        ? await api<Orden>(`/compras/ordenes/${inicial.id}`, { metodo: "PUT", cuerpo })
        : await api<Orden>("/compras/ordenes", { metodo: "POST", cuerpo: { ...cuerpo, empresa_id: empresa.id } });
      avisar(inicial ? `Orden ${o.numero} guardada.` : `Orden ${o.numero} registrada como borrador.`);
      onGuardado(o);
    } catch (err) {
      setError(err);
    } finally {
      setGuardando(false);
    }
  };

  const selectorImpuesto = (valor: string, onCambio: (v: string) => void) => (
    <label>
      Impuesto
      <select value={valor} onChange={(e) => onCambio(e.target.value)}>
        <option value="">Sin impuesto</option>
        {op.impuestos.map((i) => (
          <option key={i.id} value={i.id}>
            {i.nombre}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <form className="formulario" onSubmit={guardar}>
      <div className="fila-formulario">
        <label style={{ flexGrow: 3 }}>
          Proveedor
          <select value={cab.proveedor_id} required onChange={(e) => elegirProveedor(e.target.value)}>
            <option value="">Elige un proveedor habilitado…</option>
            {op.proveedores.map((p) => (
              <option key={p.id} value={p.id}>
                {p.razon_social} · {p.documento}
              </option>
            ))}
          </select>
        </label>
        <label>
          Contacto
          <select value={cab.contacto_id} onChange={(e) => setCab({ ...cab, contacto_id: e.target.value })} disabled={!proveedor?.contactos.length}>
            <option value="">{proveedor?.contactos.length ? "El principal" : "Sin contactos"}</option>
            {proveedor?.contactos.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="fila-formulario">
        <label>
          Unidad de negocio
          <select value={cab.unidad_negocio_id} required onChange={(e) => setCab({ ...cab, unidad_negocio_id: e.target.value })}>
            {op.unidades.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nombre}
              </option>
            ))}
          </select>
        </label>
        <label>
          Moneda
          <select value={cab.moneda} onChange={(e) => setCab({ ...cab, moneda: e.target.value })}>
            {op.monedas.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </label>
        <label>
          Condición de pago
          <select value={cab.condicion_pago_id} onChange={(e) => setCab({ ...cab, condicion_pago_id: e.target.value })}>
            <option value="">La del proveedor</option>
            {op.condiciones.map((c) => (
              <option key={c.id} value={c.id}>
                {c.nombre}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="fila-formulario">
        <label>
          <span>
            Fecha de entrega <span className="tenue">(opcional)</span>
          </span>
          <input type="date" value={cab.fecha_entrega} onChange={(e) => setCab({ ...cab, fecha_entrega: e.target.value })} />
        </label>
        <label style={{ flexGrow: 3 }}>
          <span>
            Lugar de entrega <span className="tenue">(opcional)</span>
          </span>
          <input value={cab.lugar_entrega} maxLength={300} placeholder="Almacén central, Av. …" onChange={(e) => setCab({ ...cab, lugar_entrega: e.target.value })} />
        </label>
      </div>
      <label>
        <span>
          Observaciones <span className="tenue">(se imprimen en el PDF)</span>
        </span>
        <textarea rows={2} maxLength={2000} value={cab.observaciones} onChange={(e) => setCab({ ...cab, observaciones: e.target.value })} />
      </label>
      <CamposAtributos documento={DOC} nivel="cabecera" valores={cab.atributos} onCambio={(v) => setCab({ ...cab, atributos: v })} />

      <div className="subseccion">
        <h3>Solicitudes aprobadas</h3>
        <p className="tenue">Cada solicitud entra completa, con todas sus líneas y cantidades. Desde que guardas la orden, ya no está disponible para otra.</p>
        {listaSolicitudes.length === 0 && <p className="tenue">No hay solicitudes aprobadas pendientes en esta empresa.</p>}
        {listaSolicitudes.map((s) => {
          const inc = incluidas.find((i) => i.id === s.id);
          return (
            <section key={s.id} className="linea-sol">
              <label className="opcion">
                <input type="checkbox" checked={Boolean(inc)} onChange={(e) => incluir(s, e.target.checked)} />
                <span>
                  <span className="fuerte">{s.numero}</span> {s.titulo}
                  {s.solicitante && (
                    <span className="tenue">
                      {" "}
                      · {s.solicitante} · {s.unidad_negocio} · {monto(s.total, s.moneda)}
                    </span>
                  )}
                </span>
              </label>
              {inc && (
                <div className="tabla-contenedor">
                  <table className="tabla tabla-compacta">
                    <thead>
                      <tr>
                        <th>Artículo</th>
                        <th className="numero">Cantidad</th>
                        <th>Centro</th>
                        <th>Precio ({cab.moneda})</th>
                        <th>Impuesto</th>
                      </tr>
                    </thead>
                    <tbody>
                      {inc.lineas.map((l) => (
                        <tr key={l.id}>
                          <td>
                            <span className="fuerte">{l.articulo}</span> {l.descripcion}
                          </td>
                          <td className="numero sin-corte">
                            {Number(l.cantidad)} {l.unidad}
                          </td>
                          <td>{l.centros}</td>
                          <td>
                            <input type="number" min="0" step="0.0001" aria-label={`Precio ${l.articulo}`} value={l.precio} onChange={(e) => cambiarLineaSol(s.id, l.id, { precio: e.target.value })} />
                          </td>
                          <td>
                            <select aria-label={`Impuesto ${l.articulo}`} value={l.impuesto_id} onChange={(e) => cambiarLineaSol(s.id, l.id, { impuesto_id: e.target.value })}>
                              <option value="">Sin impuesto</option>
                              {op.impuestos.map((i) => (
                                <option key={i.id} value={i.id}>
                                  {i.nombre}
                                </option>
                              ))}
                            </select>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          );
        })}
      </div>

      <div className="subseccion">
        <h3>Líneas directas</h3>
        <p className="tenue">Compras sin solicitud previa. También pasan por la aprobación de la orden.</p>
        {directas.map((d, i) => {
          const suma = d.distribuciones.reduce((a, x) => a + (Number(x.porcentaje) || 0), 0);
          const unidades = d.articulo ? [d.articulo.unidad, ...d.articulo.unidades.map((u) => u.unidad)] : [];
          return (
            <section key={d.clave} className="linea-sol" aria-label={`Línea directa ${i + 1}`}>
              <div className="linea-sol-cabecera">
                <h4>Línea directa {i + 1}</h4>
                <button type="button" className="boton boton-chico" onClick={() => setDirectas(directas.filter((x) => x.clave !== d.clave))}>
                  Quitar
                </button>
              </div>
              <BuscadorArticulo
                ruta="/compras/articulos"
                articulo={d.articulo}
                onElegir={(a) =>
                  cambiarDirecta(d.clave, {
                    articulo: a,
                    descripcion: a.descripcion,
                    unidad: a.unidad,
                    precio: a.precio_referencial && a.moneda_precio === cab.moneda ? String(Number(a.precio_referencial)) : d.precio,
                  })
                }
              />
              <div className="fila-formulario">
                <label style={{ flexGrow: 3 }}>
                  Descripción
                  <input value={d.descripcion} maxLength={240} onChange={(e) => cambiarDirecta(d.clave, { descripcion: e.target.value })} />
                </label>
                <label>
                  Cantidad
                  <input type="number" min="0" step="0.0001" required value={d.cantidad} onChange={(e) => cambiarDirecta(d.clave, { cantidad: e.target.value })} />
                </label>
                <label>
                  Unidad
                  <select value={d.unidad} disabled={!d.articulo} onChange={(e) => cambiarDirecta(d.clave, { unidad: e.target.value })}>
                    {unidades.map((u) => (
                      <option key={u} value={u}>
                        {u}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Precio ({cab.moneda})
                  <input type="number" min="0" step="0.0001" value={d.precio} onChange={(e) => cambiarDirecta(d.clave, { precio: e.target.value })} />
                </label>
                {selectorImpuesto(d.impuesto_id, (v) => cambiarDirecta(d.clave, { impuesto_id: v }))}
              </div>
              <CamposAtributos documento={DOC} nivel="linea" valores={d.atributos} onCambio={(v) => cambiarDirecta(d.clave, { atributos: v })} />
              <div className="reparto">
                <small>Centros de costo {suma !== 100 && <span className="texto-alerta">· suman {suma}, deben sumar 100</span>}</small>
                {d.distribuciones.map((r, k) => {
                  const cambiar = (c: Partial<Reparto>) => cambiarDirecta(d.clave, { distribuciones: d.distribuciones.map((x, j) => (j === k ? { ...x, ...c } : x)) });
                  return (
                    <div key={k} className="fila-formulario">
                      <label>
                        Centro de costo
                        <select value={r.centro_costo_id} required onChange={(e) => cambiar({ centro_costo_id: e.target.value })}>
                          <option value="">Elige…</option>
                          {op.centros.map((c) => (
                            <option key={c.id} value={c.id}>
                              {c.codigo} · {c.nombre}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="porcentaje">
                        %
                        <input type="number" min="0.0001" max="100" step="0.0001" required value={r.porcentaje} onChange={(e) => cambiar({ porcentaje: e.target.value })} />
                      </label>
                      {d.distribuciones.length > 1 && (
                        <button type="button" className="boton boton-chico" onClick={() => cambiarDirecta(d.clave, { distribuciones: d.distribuciones.filter((_, j) => j !== k) })}>
                          Quitar
                        </button>
                      )}
                    </div>
                  );
                })}
                <div>
                  <button
                    type="button"
                    className="boton boton-chico"
                    onClick={() => cambiarDirecta(d.clave, { distribuciones: [...d.distribuciones, { centro_costo_id: "", porcentaje: String(Math.max(0, 100 - suma)), atributos: valoresIniciales(atrReparto) }] })}
                  >
                    Repartir con otro centro
                  </button>
                </div>
              </div>
            </section>
          );
        })}
        <div>
          <button
            type="button"
            className="boton"
            onClick={() =>
              setDirectas([
                ...directas,
                {
                  clave: clave++,
                  articulo: null,
                  descripcion: "",
                  cantidad: "1",
                  unidad: "",
                  precio: "0",
                  impuesto_id: op.impuesto_defecto ?? "",
                  atributos: valoresIniciales(atrLinea),
                  distribuciones: [{ centro_costo_id: op.centros[0]?.id ?? "", porcentaje: "100", atributos: valoresIniciales(atrReparto) }],
                },
              ])
            }
          >
            Agregar línea directa
          </button>
        </div>
      </div>

      <div className="totales-oc">
        <span>Subtotal</span>
        <strong>{monto(subtotal, cab.moneda)}</strong>
        <span>Impuestos</span>
        <strong>{monto(impuesto, cab.moneda)}</strong>
        <span>Total</span>
        <strong className="total-final">{monto(subtotal + impuesto, cab.moneda)}</strong>
      </div>

      <MensajeError error={error} />
      <div className="acciones">
        <button type="button" className="boton" onClick={onCancelar}>
          Cancelar
        </button>
        <BotonAccion ocupado={guardando} disabled={incluidas.length === 0 && directas.length === 0}>
          {inicial ? "Guardar cambios" : "Guardar borrador"}
        </BotonAccion>
      </div>
    </form>
  );
}

// ---------------------------------------------------------------- detalle

function DetalleOrden({ id, onEditar, onCambio }: { id: string; onEditar: (o: Orden) => void; onCambio: () => void }) {
  const { avisar } = useAvisos();
  const [o, setO] = useState<Orden | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [ruta, setRuta] = useState<RutaAprobacion | null>(null);
  const [errorRuta, setErrorRuta] = useState<unknown>(null);
  const [comentario, setComentario] = useState("");
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [anulando, setAnulando] = useState(false);
  const [catalogo, setCatalogo] = useState<CatalogoAprobacion | null>(null);

  const cargar = useCallback(async () => {
    try {
      setO(await api<Orden>(`/compras/ordenes/${id}`));
    } catch (e) {
      setError(e);
    }
  }, [id]);
  useEffect(() => {
    cargar();
    api<CatalogoAprobacion>("/aprobaciones/catalogo").then(setCatalogo).catch(() => null);
  }, [cargar]);
  useEffect(() => {
    if (!o || !o.acciones.enviar) return;
    setErrorRuta(null);
    api<RutaAprobacion>(`/compras/ordenes/${o.id}/ruta`)
      .then(setRuta)
      .catch((e) => {
        setRuta(null);
        setErrorRuta(e);
      });
  }, [o]);

  if (!o) return <MensajeError error={error} />;
  const nombreModo = (m: string) => catalogo?.modos.find((x) => x.codigo === m)?.nombre ?? m;
  const ejecutar = async (accion: string, mensaje: string, cuerpo?: unknown) => {
    setOcupado(accion);
    setError(null);
    try {
      const nueva = await api<Orden>(`/compras/ordenes/${o.id}/${accion}`, { metodo: "POST", cuerpo: cuerpo ?? {} });
      setO(nueva);
      setComentario("");
      setAnulando(false);
      avisar(`${mensaje} ${nueva.numero}: ${ESTADOS[nueva.estado].toLowerCase()}.`);
      onCambio();
    } catch (e) {
      setError(e);
    } finally {
      setOcupado(null);
    }
  };
  const verPdf = async () => {
    setOcupado("pdf");
    try {
      await abrirPdf(o.id);
    } catch (e) {
      setError(e);
    } finally {
      setOcupado(null);
    }
  };
  const rondas = Array.from(new Set(o.pasos.map((p) => p.ronda))).sort((a, b) => b - a);

  return (
    <div className="formulario">
      <div className="linea-sol-cabecera">
        <div>
          <h3 style={{ margin: 0 }}>
            {o.numero} · {o.proveedor}
          </h3>
          <p className="tenue">
            {o.comprador} · {o.unidad_negocio} · {fechaDia(o.fecha)} · {o.condicion_pago}
            {o.fecha_entrega && ` · entrega ${fechaDia(o.fecha_entrega)}`}
          </p>
        </div>
        <EstadoOrden estado={o.estado} />
      </div>
      {o.lugar_entrega && <p>Lugar de entrega: {o.lugar_entrega}</p>}
      {o.observaciones && <p>{o.observaciones}</p>}

      <div className="tabla-contenedor">
        <table className="tabla tabla-compacta">
          <thead>
            <tr>
              <th>#</th>
              <th>Origen</th>
              <th>Artículo</th>
              <th className="numero">Cantidad</th>
              <th className="numero">Precio</th>
              <th className="numero">Imp.</th>
              <th className="numero">Total</th>
              <th>Centro</th>
            </tr>
          </thead>
          <tbody>
            {o.lineas.map((l) => (
              <tr key={l.numero}>
                <td>{l.numero}</td>
                <td className="sin-corte">{l.solicitud_numero ?? <span className="tenue">Directa</span>}</td>
                <td>
                  <span className="fuerte">{l.articulo}</span> {l.descripcion}
                </td>
                <td className="numero sin-corte">
                  {Number(l.cantidad)} {l.unidad}
                </td>
                <td className="numero">{monto(l.precio)}</td>
                <td className="numero">{Number(l.tasa)}%</td>
                <td className="numero">{monto(l.total)}</td>
                <td>{l.distribuciones.map((d) => `${d.centro_costo} ${Number(d.porcentaje)}%`).join(" · ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="totales-oc">
        <span>Subtotal</span>
        <strong>{monto(o.subtotal, o.moneda)}</strong>
        <span>Impuestos</span>
        <strong>{monto(o.impuesto, o.moneda)}</strong>
        <span>Total</span>
        <strong className="total-final">{monto(o.total, o.moneda)}</strong>
      </div>

      {o.acciones.aprobar && (
        <div className="decision">
          <strong>Tienes esta orden pendiente de aprobación</strong>
          <label>
            Comentario <span className="tenue">(obligatorio para devolver o rechazar)</span>
            <textarea rows={2} maxLength={500} value={comentario} onChange={(e) => setComentario(e.target.value)} />
          </label>
          <div className="acciones-linea">
            <BotonAccion ocupado={ocupado === "aprobar"} textoOcupado="Aprobando…" onClick={() => ejecutar("aprobar", "Aprobaste la orden", { comentario })}>
              Aprobar
            </BotonAccion>
            <BotonAccion primario={false} ocupado={ocupado === "devolver"} textoOcupado="Devolviendo…" onClick={() => ejecutar("devolver", "Devolviste la orden", { comentario })}>
              Devolver para corregir
            </BotonAccion>
            <BotonAccion primario={false} className="boton-peligro" ocupado={ocupado === "rechazar"} textoOcupado="Rechazando…" onClick={() => ejecutar("rechazar", "Rechazaste la orden", { comentario })}>
              Rechazar
            </BotonAccion>
          </div>
        </div>
      )}
      <MensajeError error={error} />

      {o.acciones.enviar && (
        <div className="subseccion">
          <h3>Quién aprobará</h3>
          {errorRuta ? (
            <MensajeError error={errorRuta} />
          ) : ruta ? (
            ruta.niveles.length === 0 ? (
              <p>Según la regla «{ruta.regla}», por su monto esta orden se aprueba al enviarla.</p>
            ) : (
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
            <HistorialRonda key={r} ronda={r} pasos={o.pasos.filter((p) => p.ronda === r)} actual={r === o.ronda} nombreModo={nombreModo} />
          ))}
        </div>
      )}

      <AsientoOrden id={o.id} />

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
            <BotonAccion className="boton-peligro" ocupado={ocupado === "anular"} textoOcupado="Anulando…" onClick={() => ejecutar("anular", "Anulaste la orden", { comentario })}>
              Anular orden
            </BotonAccion>
          </div>
        </div>
      )}

      <div className="acciones">
        <BotonAccion primario={false} ocupado={ocupado === "pdf"} textoOcupado="Generando…" onClick={verPdf}>
          Ver PDF
        </BotonAccion>
        {o.acciones.anular && !anulando && (
          <button type="button" className="boton" onClick={() => setAnulando(true)}>
            Anular
          </button>
        )}
        {o.acciones.editar && (
          <button type="button" className="boton" onClick={() => onEditar(o)}>
            Editar
          </button>
        )}
        {o.acciones.enviar && (
          <BotonAccion ocupado={ocupado === "enviar"} textoOcupado="Enviando…" disabled={Boolean(errorRuta)} onClick={() => ejecutar("enviar", "Enviaste la orden")}>
            {o.estado === "devuelta" ? "Reenviar a aprobación" : "Enviar a aprobación"}
          </BotonAccion>
        )}
        {o.acciones.marcar_enviada && (
          <BotonAccion ocupado={ocupado === "enviada"} textoOcupado="Guardando…" onClick={() => ejecutar("enviada", "Marcaste como enviada la orden")}>
            Marcar enviada al proveedor
          </BotonAccion>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- asiento contable (vista previa)

type FilaAsiento = { cuenta: string; nombre: string; centro_costo: string | null; glosa: string; debe: string; haber: string };
type AsientoPrevio = {
  moneda: string;
  moneda_funcional: string;
  tipo_cambio: string;
  asientos: { momento: string; titulo: string; filas: FilaAsiento[]; debe: string; haber: string; cuadra: boolean }[];
  avisos: string[];
};

function AsientoOrden({ id }: { id: string }) {
  const [abierto, setAbierto] = useState(false);
  const [datos, setDatos] = useState<AsientoPrevio | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    if (!abierto || datos) return;
    api<AsientoPrevio>(`/compras/ordenes/${id}/asiento`).then(setDatos).catch(setError);
  }, [abierto, datos, id]);
  return (
    <details className="subseccion asiento" onToggle={(e) => setAbierto((e.target as HTMLDetailsElement).open)}>
      <summary>
        <h3>Asiento contable (vista previa)</h3>
      </summary>
      <MensajeError error={error} />
      {datos && (
        <>
          <p className="tenue">
            No se contabiliza: muestra cómo quedará el registro según la configuración de Contabilidad (Configuración › Cuentas por pagar).
            Importes en {datos.moneda}.
          </p>
          {datos.avisos.map((a) => (
            <p key={a} className="aviso aviso-advertencia">
              {a}
            </p>
          ))}
          {datos.asientos.map((a) => (
            <div key={a.momento} className="tabla-contenedor">
              <table className="tabla tabla-compacta">
                <caption>{a.titulo}</caption>
                <thead>
                  <tr>
                    <th>Cuenta</th>
                    <th>Centro</th>
                    <th>Glosa</th>
                    <th className="numero">Debe</th>
                    <th className="numero">Haber</th>
                  </tr>
                </thead>
                <tbody>
                  {a.filas.map((f, i) => (
                    <tr key={i}>
                      <td>
                        <span className="fuerte">{f.cuenta}</span> {f.nombre}
                      </td>
                      <td>{f.centro_costo ?? ""}</td>
                      <td>{f.glosa}</td>
                      <td className="numero">{Number(f.debe) ? monto(f.debe) : ""}</td>
                      <td className="numero">{Number(f.haber) ? monto(f.haber) : ""}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th colSpan={3}>{a.cuadra ? "Totales" : "Totales · no cuadra, revisa la configuración"}</th>
                    <th className="numero">{monto(a.debe)}</th>
                    <th className="numero">{monto(a.haber)}</th>
                  </tr>
                </tfoot>
              </table>
            </div>
          ))}
        </>
      )}
    </details>
  );
}
