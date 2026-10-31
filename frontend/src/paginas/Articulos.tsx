import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  api,
  cuentaTexto,
  decimal,
  NOMBRE_TIPO_ARTICULO,
  type Articulo,
  type ArticuloResumen,
  type Categoria,
  type EstadoContable,
  type Moneda,
  type PerfilContable,
  type UnidadMedida,
} from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { useSesion } from "../sesion";

type Datos = {
  codigo: string;
  descripcion: string;
  tipo: string;
  categoria_id: string;
  unidad: string;
  impuesto: string;
  marca: string;
  modelo: string;
  especificacion: string;
  precio_referencial: string;
  moneda_precio: string;
};
const VACIO: Datos = {
  codigo: "",
  descripcion: "",
  tipo: "bien_no_inventariable",
  categoria_id: "",
  unidad: "UND",
  impuesto: "IGV18",
  marca: "",
  modelo: "",
  especificacion: "",
  precio_referencial: "",
  moneda_precio: "PEN",
};

export default function Articulos() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const crearPerm = puede("maestros.articulo.crear");
  const editar = puede("maestros.articulo.editar");
  const excepcionPerm = puede("contabilidad.perfil.editar");

  const [lista, setLista] = useState<ArticuloResumen[]>([]);
  const [buscar, setBuscar] = useState("");
  const [filtroCat, setFiltroCat] = useState("");
  const [filtroTipo, setFiltroTipo] = useState("");
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [unidades, setUnidades] = useState<UnidadMedida[]>([]);
  const [monedas, setMonedas] = useState<Moneda[]>([]);
  const [impuestos, setImpuestos] = useState<string[]>(["IGV18"]);
  const [error, setError] = useState<unknown>(null);

  const [abierto, setAbierto] = useState<Articulo | "nuevo" | null>(null);
  const [datos, setDatos] = useState<Datos>(VACIO);
  const [sugerido, setSugerido] = useState("");
  const [estado, setEstado] = useState<EstadoContable[]>([]);
  const [perfilesEmpresa, setPerfilesEmpresa] = useState<Record<string, PerfilContable[]>>({});
  const [alternas, setAlternas] = useState<{ unidad: string; factor: string }[]>([]);
  const [errorPanel, setErrorPanel] = useState<unknown>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    const q = new URLSearchParams();
    if (buscar.trim()) q.set("buscar", buscar.trim());
    if (filtroCat) q.set("categoria_id", filtroCat);
    if (filtroTipo) q.set("tipo", filtroTipo);
    try {
      setLista(await api<ArticuloResumen[]>(`/maestros/articulos?${q}`));
    } catch (e) {
      setError(e);
    }
  }, [buscar, filtroCat, filtroTipo]);
  useEffect(() => {
    const t = window.setTimeout(cargar, 250);
    return () => window.clearTimeout(t);
  }, [cargar]);

  useEffect(() => {
    if (puede("maestros.categoria.ver")) api<Categoria[]>("/maestros/categorias").then(setCategorias).catch(setError);
    if (puede("maestros.unidad.ver")) api<UnidadMedida[]>("/maestros/unidades-medida").then(setUnidades).catch(setError);
    if (puede("maestros.moneda.ver")) api<Moneda[]>("/maestros/monedas").then(setMonedas).catch(setError);
    api<string[]>("/contabilidad/impuestos/codigos")
      .then((c) => c.length && setImpuestos(c))
      .catch(() => undefined);
  }, [puede]);

  // Código sugerido al elegir la categoría de un artículo nuevo
  useEffect(() => {
    if (abierto !== "nuevo" || !datos.categoria_id) return setSugerido("");
    api<{ codigo: string }>(`/maestros/articulos/siguiente-codigo?categoria_id=${datos.categoria_id}`)
      .then((r) => setSugerido(r.codigo))
      .catch(() => setSugerido(""));
  }, [abierto, datos.categoria_id]);

  const cargarEstado = async (id: string) => {
    const filas = await api<EstadoContable[]>(`/contabilidad/articulos/${id}/estado`);
    setEstado(filas);
    if (excepcionPerm) {
      const pares = await Promise.all(
        filas.map(async (f) => [f.empresa_id, await api<PerfilContable[]>(`/contabilidad/empresas/${f.empresa_id}/perfiles`)] as const),
      );
      setPerfilesEmpresa(Object.fromEntries(pares));
    }
  };

  const mostrar = async (a: Articulo) => {
    setAbierto(a);
    setDatos({
      codigo: a.codigo,
      descripcion: a.descripcion,
      tipo: a.tipo,
      categoria_id: a.categoria.id,
      unidad: a.unidad,
      impuesto: a.impuesto,
      marca: a.marca ?? "",
      modelo: a.modelo ?? "",
      especificacion: a.especificacion ?? "",
      precio_referencial: a.precio_referencial ? decimal(a.precio_referencial) : "",
      moneda_precio: a.moneda_precio ?? "PEN",
    });
    setAlternas(a.unidades_alternas.map((u) => ({ unidad: u.unidad, factor: decimal(u.factor) })));
    try {
      await cargarEstado(a.id);
    } catch (e) {
      setErrorPanel(e);
    }
  };
  const abrirFicha = async (id: string) => {
    setErrorPanel(null);
    try {
      await mostrar(await api<Articulo>(`/maestros/articulos/${id}`));
    } catch (e) {
      setError(e);
    }
  };
  const nuevo = () => {
    setErrorPanel(null);
    setEstado([]);
    setAbierto("nuevo");
    setDatos({ ...VACIO, categoria_id: filtroCat });
  };
  const cerrar = useCallback(() => setAbierto(null), []);
  const ficha = abierto && abierto !== "nuevo" ? abierto : null;

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setOcupado("datos");
    setErrorPanel(null);
    const conPrecio = datos.precio_referencial.trim() !== "";
    const cuerpo = {
      descripcion: datos.descripcion,
      tipo: datos.tipo,
      categoria_id: datos.categoria_id,
      unidad: datos.unidad,
      impuesto: datos.impuesto,
      marca: datos.marca,
      modelo: datos.modelo,
      especificacion: datos.especificacion,
      precio_referencial: conPrecio ? datos.precio_referencial : null,
      moneda_precio: conPrecio ? datos.moneda_precio : null,
    };
    try {
      const a = ficha
        ? await api<Articulo>(`/maestros/articulos/${ficha.id}`, { metodo: "PATCH", cuerpo })
        : await api<Articulo>("/maestros/articulos", { metodo: "POST", cuerpo: { ...cuerpo, codigo: datos.codigo || null } });
      avisar(ficha ? `Artículo ${a.codigo} guardado.` : `Artículo ${a.codigo} registrado.`);
      await mostrar(a);
      await cargar();
    } catch (err) {
      setErrorPanel(err);
    } finally {
      setOcupado(null);
    }
  };

  const cambiarEstado = async (activo: boolean) => {
    if (!ficha) return;
    setOcupado("estado");
    try {
      const a = await api<Articulo>(`/maestros/articulos/${ficha.id}`, { metodo: "PATCH", cuerpo: { activo } });
      avisar(activo ? "Artículo reactivado." : "Artículo desactivado.");
      await mostrar(a);
      await cargar();
    } catch (err) {
      setErrorPanel(err);
    } finally {
      setOcupado(null);
    }
  };

  const guardarAlternas = async () => {
    if (!ficha) return;
    setOcupado("unidades");
    setErrorPanel(null);
    try {
      const a = await api<Articulo>(`/maestros/articulos/${ficha.id}/unidades`, {
        metodo: "PUT",
        cuerpo: { unidades: alternas.filter((u) => u.unidad && u.factor) },
      });
      avisar("Unidades alternativas guardadas.");
      await mostrar(a);
    } catch (err) {
      setErrorPanel(err);
    } finally {
      setOcupado(null);
    }
  };

  const excepcion = async (empresaId: string, perfilId: string) => {
    if (!ficha) return;
    setOcupado(`exc-${empresaId}`);
    setErrorPanel(null);
    try {
      setEstado(
        await api<EstadoContable[]>(`/contabilidad/empresas/${empresaId}/articulos/${ficha.id}/perfil`, {
          metodo: "PUT",
          cuerpo: { perfil_id: perfilId || null },
        }),
      );
      avisar(perfilId ? "Excepción contable guardada." : "El artículo vuelve a usar el perfil de su categoría.");
    } catch (err) {
      setErrorPanel(err);
    } finally {
      setOcupado(null);
    }
  };

  const unidadesActivas = unidades.filter((u) => u.activo);
  const categoriasActivas = categorias.filter((c) => c.activo || c.id === datos.categoria_id);
  const soloLectura = !!ficha && !editar;

  return (
    <>
      <Encabezado
        titulo="Artículos"
        descripcion="Bienes y servicios que se compran, comunes a todas las empresas. Sus cuentas contables salen del perfil de su categoría en cada empresa."
        accion={
          crearPerm && (
            <button className="boton boton-primario" onClick={nuevo}>
              Registrar artículo
            </button>
          )
        }
      />
      <div className="barra-filtros">
        <label className="filtro buscador">
          Buscar
          <input value={buscar} placeholder="Código, descripción, marca o modelo" onChange={(e) => setBuscar(e.target.value)} />
        </label>
        <label className="filtro">
          Categoría
          <select value={filtroCat} onChange={(e) => setFiltroCat(e.target.value)}>
            <option value="">Todas</option>
            {categorias.map((c) => (
              <option key={c.id} value={c.id}>
                {"  ".repeat(c.nivel - 1)}
                {c.nombre}
              </option>
            ))}
          </select>
        </label>
        <label className="filtro">
          Tipo
          <select value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
            <option value="">Todos</option>
            {Object.entries(NOMBRE_TIPO_ARTICULO).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      </div>
      <MensajeError error={error} />
      {lista.length === 0 ? (
        <div className="vacio">
          <p>{buscar || filtroCat || filtroTipo ? "Ningún artículo coincide con los filtros." : "Aún no hay artículos registrados."}</p>
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Código</th>
                <th>Descripción</th>
                <th>Categoría</th>
                <th>Tipo</th>
                <th>Unidad</th>
                <th className="numero">Precio ref.</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((a) => (
                <tr key={a.id} onClick={() => abrirFicha(a.id)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrirFicha(a.id)}>
                  <td className="fuerte sin-corte">{a.codigo}</td>
                  <td>{a.descripcion}</td>
                  <td>{a.categoria.nombre}</td>
                  <td>{NOMBRE_TIPO_ARTICULO[a.tipo]}</td>
                  <td>{a.unidad}</td>
                  <td className="numero">{a.precio_referencial ? `${a.moneda_precio} ${decimal(a.precio_referencial)}` : "—"}</td>
                  <td>
                    <Estado activo={a.activo} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel titulo={ficha ? `${ficha.codigo} · ${ficha.descripcion}` : "Registrar artículo"} abierto={abierto !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          <div className="fila-doble">
            <label>
              Categoría
              <select value={datos.categoria_id} required disabled={soloLectura} onChange={(e) => setDatos({ ...datos, categoria_id: e.target.value })}>
                <option value="">Elegir…</option>
                {categoriasActivas.map((c) => (
                  <option key={c.id} value={c.id}>
                    {"  ".repeat(c.nivel - 1)}
                    {c.codigo} · {c.nombre}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Código
              <input
                value={datos.codigo}
                disabled={!!ficha}
                maxLength={30}
                placeholder={sugerido ? `${sugerido} (automático)` : "Automático"}
                onChange={(e) => setDatos({ ...datos, codigo: e.target.value.toUpperCase() })}
              />
              {!ficha && <small>Déjalo vacío para usar el correlativo de la categoría.</small>}
            </label>
          </div>
          <label>
            Descripción
            <input value={datos.descripcion} required maxLength={240} disabled={soloLectura} onChange={(e) => setDatos({ ...datos, descripcion: e.target.value })} />
          </label>
          <div className="fila-doble">
            <label>
              Tipo
              <select value={datos.tipo} disabled={soloLectura} onChange={(e) => setDatos({ ...datos, tipo: e.target.value })}>
                {Object.entries(NOMBRE_TIPO_ARTICULO).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
              <small>Debe coincidir con el perfil contable de la categoría.</small>
            </label>
            <label>
              Unidad de medida
              <select value={datos.unidad} disabled={soloLectura} onChange={(e) => setDatos({ ...datos, unidad: e.target.value })}>
                {(unidadesActivas.length ? unidadesActivas : [{ codigo: datos.unidad, nombre: "" }]).map((u) => (
                  <option key={u.codigo} value={u.codigo}>
                    {u.codigo} {u.nombre && `— ${u.nombre}`}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="fila-doble">
            <label>
              <span>
                Marca <span className="tenue">(opcional)</span>
              </span>
              <input value={datos.marca} maxLength={100} disabled={soloLectura} onChange={(e) => setDatos({ ...datos, marca: e.target.value })} />
            </label>
            <label>
              <span>
                Modelo <span className="tenue">(opcional)</span>
              </span>
              <input value={datos.modelo} maxLength={100} disabled={soloLectura} onChange={(e) => setDatos({ ...datos, modelo: e.target.value })} />
            </label>
          </div>
          <label>
            <span>
              Especificación técnica <span className="tenue">(opcional)</span>
            </span>
            <textarea
              rows={3}
              maxLength={4000}
              value={datos.especificacion}
              disabled={soloLectura}
              placeholder="Medidas, normas, calidad… Se enviará al proveedor con la orden de compra."
              onChange={(e) => setDatos({ ...datos, especificacion: e.target.value })}
            />
          </label>
          <div className="fila-doble">
            <label>
              <span>
                Precio referencial <span className="tenue">(opcional)</span>
              </span>
              <div className="entrada-con-moneda">
                <select value={datos.moneda_precio} disabled={soloLectura} onChange={(e) => setDatos({ ...datos, moneda_precio: e.target.value })}>
                  {monedas
                    .filter((m) => m.activo)
                    .map((m) => (
                      <option key={m.codigo} value={m.codigo}>
                        {m.codigo}
                      </option>
                    ))}
                </select>
                <input
                  type="number"
                  inputMode="decimal"
                  min={0}
                  step="0.0001"
                  value={datos.precio_referencial}
                  disabled={soloLectura}
                  onChange={(e) => setDatos({ ...datos, precio_referencial: e.target.value })}
                />
              </div>
              <small>Las solicitudes lo usan para estimar el monto.</small>
            </label>
            <label>
              Impuesto
              <select value={datos.impuesto} disabled={soloLectura} onChange={(e) => setDatos({ ...datos, impuesto: e.target.value })}>
                {[...new Set([datos.impuesto, ...impuestos])].map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {!ficha && <MensajeError error={errorPanel} />}
          {(!ficha ? crearPerm : editar) && (
            <div className="acciones">
              {ficha && (
                <button type="button" className="boton" style={{ marginRight: "auto" }} disabled={ocupado !== null} onClick={() => cambiarEstado(!ficha.activo)}>
                  {ficha.activo ? "Desactivar artículo" : "Reactivar artículo"}
                </button>
              )}
              <BotonAccion ocupado={ocupado === "datos"} textoOcupado={ficha ? "Guardando…" : "Registrando…"}>
                {ficha ? "Guardar datos" : "Registrar artículo"}
              </BotonAccion>
            </div>
          )}
        </form>

        {ficha && (
          <>
            <MensajeError error={errorPanel} />
            <section className="subseccion">
              <h3>Configuración contable por empresa</h3>
              <p className="tenue">De dónde salen las cuentas de este artículo en cada empresa y si ya se puede comprar.</p>
              <ul className="lista-simple">
                {estado.map((f) => (
                  <li key={f.empresa_id} className="li-estado">
                    <div>
                      <p className="fuerte">
                        {f.razon_social}{" "}
                        {f.problema ? <span className="etiqueta etiqueta-alerta">No se puede comprar</span> : <span className="etiqueta etiqueta-estandar">Listo para comprar</span>}
                      </p>
                      {f.problema && <p className="texto-alerta">{f.problema}</p>}
                      {f.perfil && (
                        <p className="tenue">
                          {f.perfil.nombre} ({f.origen}) · Cargo {cuentaTexto(f.perfil.cuenta_cargo)} · Por pagar {f.perfil.cuenta_por_pagar.codigo}
                          {f.impuesto && ` · ${f.impuesto.nombre}`}
                        </p>
                      )}
                      {excepcionPerm && perfilesEmpresa[f.empresa_id] && (
                        <label className="filtro excepcion">
                          Perfil
                          <select
                            value={f.excepcion ? (f.perfil?.id ?? "") : ""}
                            disabled={ocupado !== null}
                            onChange={(e) => excepcion(f.empresa_id, e.target.value)}
                          >
                            <option value="">El de su categoría</option>
                            {perfilesEmpresa[f.empresa_id]
                              .filter((p) => p.activo && p.tipo_articulo === ficha.tipo)
                              .map((p) => (
                                <option key={p.id} value={p.id}>
                                  Excepción: {p.nombre}
                                </option>
                              ))}
                          </select>
                        </label>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            <section className="subseccion">
              <h3>Unidades alternativas</h3>
              <p className="tenue">
                Para pedir en una unidad y recibir en otra. Ej.: 1 CJA = 12 {ficha.unidad}. Las conversiones generales (1 DOC = 12 UND) ya se aplican
                solas.
              </p>
              {alternas.map((u, i) => (
                <div key={i} className="fila-alterna">
                  <span>1</span>
                  <select
                    value={u.unidad}
                    disabled={!editar}
                    onChange={(e) => setAlternas(alternas.map((x, j) => (j === i ? { ...x, unidad: e.target.value } : x)))}
                  >
                    <option value="">Unidad…</option>
                    {unidadesActivas
                      .filter((x) => x.codigo !== ficha.unidad)
                      .map((x) => (
                        <option key={x.codigo} value={x.codigo}>
                          {x.codigo} — {x.nombre}
                        </option>
                      ))}
                  </select>
                  <span>=</span>
                  <input
                    type="number"
                    min="0.000001"
                    step="0.000001"
                    value={u.factor}
                    disabled={!editar}
                    onChange={(e) => setAlternas(alternas.map((x, j) => (j === i ? { ...x, factor: e.target.value } : x)))}
                  />
                  <span>{ficha.unidad}</span>
                  {editar && (
                    <button className="enlace" onClick={() => setAlternas(alternas.filter((_, j) => j !== i))}>
                      Quitar
                    </button>
                  )}
                </div>
              ))}
              {editar && (
                <div className="acciones-linea">
                  <button className="boton" onClick={() => setAlternas([...alternas, { unidad: "", factor: "" }])}>
                    + Agregar unidad
                  </button>
                  <BotonAccion primario={false} ocupado={ocupado === "unidades"} onClick={guardarAlternas}>
                    Guardar unidades
                  </BotonAccion>
                </div>
              )}
            </section>
          </>
        )}
      </Panel>
    </>
  );
}
