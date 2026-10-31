import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  api,
  NOMBRE_TIPO_CUENTA,
  nombrePais,
  type Categoria,
  type CondicionPago,
  type ContactoProveedor,
  type Moneda,
  type Proveedor,
  type ProveedorResumen,
  type TipoDocumento,
} from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { type EmpresaResumen } from "../empresa";
import { useSesion } from "../sesion";

type Datos = {
  tipo_documento: string;
  numero_documento: string;
  pais: string;
  razon_social: string;
  nombre_comercial: string;
  direccion: string;
  correo: string;
  telefono: string;
  moneda: string;
  condicion_pago_id: string;
};
const VACIO: Datos = {
  tipo_documento: "RUC",
  numero_documento: "",
  pais: "",
  razon_social: "",
  nombre_comercial: "",
  direccion: "",
  correo: "",
  telefono: "",
  moneda: "PEN",
  condicion_pago_id: "",
};
const CONTACTO_VACIO = { nombre: "", cargo: "", correo: "", telefono: "" };
const CUENTA_VACIA = { banco: "", tipo: "corriente", moneda: "PEN", numero: "", cci: "", swift: "" };

export default function Proveedores() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const crear = puede("maestros.proveedor.crear");
  const editar = puede("maestros.proveedor.editar");
  const banco = puede("maestros.proveedor.banco");

  const [lista, setLista] = useState<ProveedorResumen[]>([]);
  const [buscar, setBuscar] = useState("");
  const [tipos, setTipos] = useState<TipoDocumento[]>([]);
  const [condiciones, setCondiciones] = useState<CondicionPago[]>([]);
  const [monedas, setMonedas] = useState<Moneda[]>([]);
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [empresas, setEmpresas] = useState<EmpresaResumen[]>([]);
  const [error, setError] = useState<unknown>(null);

  const [abierto, setAbierto] = useState<Proveedor | "nuevo" | null>(null);
  const [datos, setDatos] = useState<Datos>(VACIO);
  const [errorPanel, setErrorPanel] = useState<unknown>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [contacto, setContacto] = useState(CONTACTO_VACIO);
  const [cuenta, setCuenta] = useState(CUENTA_VACIA);
  const [cats, setCats] = useState<Set<string>>(new Set());
  const [motivos, setMotivos] = useState<Record<string, string>>({});

  const cargar = useCallback(async () => {
    try {
      setLista(await api<ProveedorResumen[]>(`/maestros/proveedores${buscar.trim() ? `?buscar=${encodeURIComponent(buscar.trim())}` : ""}`));
    } catch (e) {
      setError(e);
    }
  }, [buscar]);
  useEffect(() => {
    const t = window.setTimeout(cargar, 250);
    return () => window.clearTimeout(t);
  }, [cargar]);

  useEffect(() => {
    const opcional = <T,>(permiso: string, ruta: string, fijar: (v: T) => void) =>
      puede(permiso) ? api<T>(ruta).then(fijar).catch(setError) : undefined;
    api<TipoDocumento[]>("/maestros/tipos-documento").then(setTipos).catch(setError);
    api<CondicionPago[]>("/maestros/condiciones-pago").then(setCondiciones).catch(setError);
    api<EmpresaResumen[]>("/maestros/empresas/accesibles").then(setEmpresas).catch(setError);
    opcional<Moneda[]>("maestros.moneda.ver", "/maestros/monedas", setMonedas);
    opcional<Categoria[]>("maestros.categoria.ver", "/maestros/categorias", setCategorias);
  }, [puede]);

  const abrirFicha = async (id: string) => {
    setErrorPanel(null);
    try {
      const p = await api<Proveedor>(`/maestros/proveedores/${id}`);
      mostrar(p);
    } catch (e) {
      setError(e);
    }
  };
  const mostrar = (p: Proveedor) => {
    setAbierto(p);
    setDatos({
      tipo_documento: p.tipo_documento,
      numero_documento: p.numero_documento,
      pais: p.pais,
      razon_social: p.razon_social,
      nombre_comercial: p.nombre_comercial ?? "",
      direccion: p.direccion ?? "",
      correo: p.correo ?? "",
      telefono: p.telefono ?? "",
      moneda: p.moneda,
      condicion_pago_id: p.condicion_pago.id,
    });
    setCats(new Set(p.categorias.map((c) => c.id)));
    setContacto(CONTACTO_VACIO);
    setCuenta({ ...CUENTA_VACIA, moneda: p.moneda });
  };
  const nuevo = () => {
    setErrorPanel(null);
    setAbierto("nuevo");
    setDatos({ ...VACIO, condicion_pago_id: condiciones.find((c) => c.codigo === "CONTADO")?.id ?? "" });
  };
  const cerrar = useCallback(() => setAbierto(null), []);
  const ficha = abierto && abierto !== "nuevo" ? abierto : null;
  const tipo = tipos.find((t) => t.codigo === datos.tipo_documento);
  const local = ficha ? ficha.pais === "pe" : !tipo?.extranjero;

  /** Ejecuta una acción del panel, avisa y refresca la ficha y la lista. */
  const accion = async (clave: string, fn: () => Promise<Proveedor | unknown>, exito: string) => {
    setOcupado(clave);
    setErrorPanel(null);
    try {
      const r = await fn();
      avisar(exito);
      if (r && typeof r === "object" && "razon_social" in r) mostrar(r as Proveedor);
      else if (ficha) await abrirFicha(ficha.id);
      await cargar();
      return true;
    } catch (e) {
      setErrorPanel(e);
      return false;
    } finally {
      setOcupado(null);
    }
  };

  const guardarDatos = (e: FormEvent) => {
    e.preventDefault();
    const cuerpo = {
      razon_social: datos.razon_social,
      nombre_comercial: datos.nombre_comercial,
      direccion: datos.direccion,
      correo: datos.correo,
      telefono: datos.telefono,
      moneda: datos.moneda,
      condicion_pago_id: datos.condicion_pago_id || null,
    };
    if (ficha) {
      accion("datos", () => api<Proveedor>(`/maestros/proveedores/${ficha.id}`, { metodo: "PATCH", cuerpo }), "Datos del proveedor guardados.");
    } else {
      accion(
        "datos",
        () =>
          api<Proveedor>("/maestros/proveedores", {
            metodo: "POST",
            cuerpo: {
              ...cuerpo,
              tipo_documento: datos.tipo_documento,
              numero_documento: datos.numero_documento,
              pais: tipo?.extranjero ? datos.pais : null,
              moneda: datos.moneda || null,
            },
          }),
        `Proveedor ${datos.razon_social} registrado. Agrega sus contactos y cuentas.`,
      );
    }
  };

  const agregarContacto = async (e: FormEvent) => {
    e.preventDefault();
    if (!ficha) return;
    const ok = await accion(
      "contacto",
      () => api(`/maestros/proveedores/${ficha.id}/contactos`, { metodo: "POST", cuerpo: contacto }),
      `Contacto ${contacto.nombre} agregado.`,
    );
    if (ok) setContacto(CONTACTO_VACIO);
  };
  const hacerPrincipal = (c: ContactoProveedor) =>
    accion(`principal-${c.id}`, () => api(`/maestros/contactos/${c.id}`, { metodo: "PATCH", cuerpo: { principal: true } }), `${c.nombre} es ahora el contacto principal.`);
  const quitarContacto = (c: ContactoProveedor) =>
    accion(`quitar-${c.id}`, () => api(`/maestros/contactos/${c.id}`, { metodo: "DELETE" }), `Contacto ${c.nombre} quitado.`);

  const agregarCuenta = async (e: FormEvent) => {
    e.preventDefault();
    if (!ficha) return;
    const ok = await accion(
      "cuenta",
      () =>
        api(`/maestros/proveedores/${ficha.id}/cuentas-bancarias`, {
          metodo: "POST",
          cuerpo: { ...cuenta, cci: local ? cuenta.cci : null, swift: local ? cuenta.swift || null : cuenta.swift },
        }),
      "Cuenta bancaria registrada.",
    );
    if (ok) setCuenta({ ...CUENTA_VACIA, moneda: ficha.moneda });
  };
  const cambiarCuenta = (id: string, activo: boolean) =>
    accion(`cuenta-${id}`, () => api(`/maestros/cuentas-bancarias/${id}`, { metodo: "PATCH", cuerpo: { activo } }), activo ? "Cuenta reactivada." : "Cuenta desactivada.");

  const guardarCategorias = () =>
    ficha &&
    accion(
      "categorias",
      () => api<Proveedor>(`/maestros/proveedores/${ficha.id}/categorias`, { metodo: "PUT", cuerpo: { categoria_ids: [...cats] } }),
      "Categorías del proveedor guardadas.",
    );
  const bloquear = (empresa: EmpresaResumen, bloqueado: boolean) =>
    ficha &&
    accion(
      `bloqueo-${empresa.id}`,
      () =>
        api<Proveedor>(`/maestros/proveedores/${ficha.id}/empresas/${empresa.id}`, {
          metodo: "PUT",
          cuerpo: { bloqueado, motivo: motivos[empresa.id] ?? null },
        }),
      bloqueado ? `Proveedor bloqueado para ${empresa.razon_social}.` : `Proveedor habilitado para ${empresa.razon_social}.`,
    );
  const cambiarEstado = (activo: boolean) =>
    ficha &&
    accion("estado", () => api<Proveedor>(`/maestros/proveedores/${ficha.id}`, { metodo: "PATCH", cuerpo: { activo } }), activo ? "Proveedor reactivado." : "Proveedor desactivado.");

  const catsOrdenadas = useMemo(() => categorias.filter((c) => c.activo), [categorias]);
  const catsSinCambios = ficha ? [...cats].sort().join() === ficha.categorias.map((c) => c.id).sort().join() : true;
  const monedasActivas = monedas.filter((m) => m.activo);
  const nombreEmpresa = (id: string) => empresas.find((e) => e.id === id)?.razon_social ?? "otra empresa";

  return (
    <>
      <Encabezado
        titulo="Proveedores"
        descripcion="Proveedores compartidos por todas las empresas del grupo. Cada empresa puede bloquear a un proveedor para sí."
        accion={
          crear && (
            <button className="boton boton-primario" onClick={nuevo}>
              Registrar proveedor
            </button>
          )
        }
      />
      <div className="barra-filtros">
        <label className="filtro buscador">
          Buscar
          <input value={buscar} placeholder="Razón social, nombre comercial o documento" onChange={(e) => setBuscar(e.target.value)} />
        </label>
      </div>
      <MensajeError error={error} />
      {lista.length === 0 ? (
        <div className="vacio">
          <p>{buscar ? "Ningún proveedor coincide con la búsqueda." : "Aún no hay proveedores registrados."}</p>
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Proveedor</th>
                <th>Documento</th>
                <th>Moneda</th>
                <th>Condición de pago</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((p) => (
                <tr key={p.id} onClick={() => abrirFicha(p.id)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrirFicha(p.id)}>
                  <td>
                    <span className="fuerte">{p.razon_social}</span>
                    {p.nombre_comercial && <p className="tenue">{p.nombre_comercial}</p>}
                  </td>
                  <td className="numero">
                    {p.tipo_documento} {p.numero_documento}
                    {p.pais !== "pe" && <p className="tenue">{nombrePais(p.pais)}</p>}
                  </td>
                  <td>{p.moneda}</td>
                  <td>{p.condicion_pago.nombre}</td>
                  <td>
                    <Estado activo={p.activo} />
                    {p.bloqueos.length > 0 && (
                      <p>
                        <span className="etiqueta etiqueta-alerta">
                          Bloqueado en {p.bloqueos.length === 1 ? nombreEmpresa(p.bloqueos[0].empresa_id) : `${p.bloqueos.length} empresas`}
                        </span>
                      </p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel titulo={ficha ? ficha.razon_social : "Registrar proveedor"} abierto={abierto !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardarDatos}>
          <div className="fila-doble">
            <label>
              Tipo de documento
              <select
                value={datos.tipo_documento}
                disabled={!!ficha}
                onChange={(e) => {
                  const t = tipos.find((x) => x.codigo === e.target.value);
                  setDatos({ ...datos, tipo_documento: e.target.value, moneda: t?.extranjero ? "USD" : "PEN" });
                }}
              >
                {tipos.map((t) => (
                  <option key={t.codigo} value={t.codigo}>
                    {t.nombre}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Número
              <input
                value={datos.numero_documento}
                required
                disabled={!!ficha}
                maxLength={25}
                inputMode={tipo?.extranjero ? "text" : "numeric"}
                placeholder={datos.tipo_documento === "RUC" ? "11 dígitos" : datos.tipo_documento === "DNI" ? "8 dígitos" : "Tax ID"}
                onChange={(e) => setDatos({ ...datos, numero_documento: e.target.value })}
              />
            </label>
          </div>
          {(tipo?.extranjero || (ficha && ficha.pais !== "pe")) && (
            <label>
              País del proveedor
              <input
                value={ficha ? nombrePais(ficha.pais) : datos.pais}
                required
                disabled={!!ficha}
                maxLength={2}
                placeholder="Código de 2 letras: US, CN, DE…"
                onChange={(e) => setDatos({ ...datos, pais: e.target.value.toUpperCase().replace(/[^A-Z]/g, "") })}
              />
              {!ficha && datos.pais.length === 2 && <small>{nombrePais(datos.pais)}</small>}
            </label>
          )}
          {ficha && <small className="tenue">El documento y el país no cambian: identifican al proveedor ante el fisco.</small>}
          <label>
            Razón social
            <input value={datos.razon_social} required maxLength={200} disabled={!!ficha && !editar} onChange={(e) => setDatos({ ...datos, razon_social: e.target.value })} />
          </label>
          <label>
            <span>
              Nombre comercial <span className="tenue">(opcional)</span>
            </span>
            <input value={datos.nombre_comercial} maxLength={150} disabled={!!ficha && !editar} onChange={(e) => setDatos({ ...datos, nombre_comercial: e.target.value })} />
          </label>
          <label>
            <span>
              Dirección <span className="tenue">(opcional)</span>
            </span>
            <input value={datos.direccion} maxLength={300} disabled={!!ficha && !editar} onChange={(e) => setDatos({ ...datos, direccion: e.target.value })} />
          </label>
          <div className="fila-doble">
            <label>
              <span>
                Correo <span className="tenue">(opcional)</span>
              </span>
              <input type="email" value={datos.correo} maxLength={200} disabled={!!ficha && !editar} onChange={(e) => setDatos({ ...datos, correo: e.target.value })} />
            </label>
            <label>
              <span>
                Teléfono <span className="tenue">(opcional)</span>
              </span>
              <input value={datos.telefono} maxLength={40} disabled={!!ficha && !editar} onChange={(e) => setDatos({ ...datos, telefono: e.target.value })} />
            </label>
          </div>
          <div className="fila-doble">
            <label>
              Moneda habitual
              <select value={datos.moneda} disabled={!!ficha && !editar} onChange={(e) => setDatos({ ...datos, moneda: e.target.value })}>
                {(monedasActivas.length ? monedasActivas : [{ codigo: datos.moneda, nombre: "" }]).map((m) => (
                  <option key={m.codigo} value={m.codigo}>
                    {m.codigo}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Condición de pago
              <select value={datos.condicion_pago_id} disabled={!!ficha && !editar} onChange={(e) => setDatos({ ...datos, condicion_pago_id: e.target.value })}>
                {condiciones
                  .filter((c) => c.activo || c.id === datos.condicion_pago_id)
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.nombre}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <small className="tenue">La orden de compra tomará la moneda y la condición de pago del proveedor por defecto.</small>
          {(!ficha || editar) && (
            <div className="acciones">
              {ficha && (
                <button type="button" className="boton" style={{ marginRight: "auto" }} onClick={() => cambiarEstado(!ficha.activo)}>
                  {ficha.activo ? "Desactivar proveedor" : "Reactivar proveedor"}
                </button>
              )}
              <BotonAccion ocupado={ocupado === "datos"} textoOcupado={ficha ? "Guardando…" : "Registrando…"}>
                {ficha ? "Guardar datos" : "Registrar proveedor"}
              </BotonAccion>
            </div>
          )}
        </form>
        {!ficha && <MensajeError error={errorPanel} />}

        {ficha && (
          <>
            <MensajeError error={errorPanel} />

            <section className="subseccion">
              <h3>Contactos</h3>
              <p className="tenue">El contacto principal recibirá las órdenes de compra.</p>
              {ficha.contactos.length > 0 && (
                <ul className="lista-simple">
                  {ficha.contactos.map((c) => (
                    <li key={c.id}>
                      <div>
                        <p className="fuerte">
                          {c.nombre} {c.principal && <span className="etiqueta etiqueta-estandar">Principal</span>}
                        </p>
                        <p className="tenue">{[c.cargo, c.correo, c.telefono].filter(Boolean).join(" · ") || "Sin datos de contacto"}</p>
                      </div>
                      {editar && (
                        <div className="acciones-linea">
                          {!c.principal && (
                            <button className="enlace" disabled={ocupado !== null} onClick={() => hacerPrincipal(c)}>
                              Hacer principal
                            </button>
                          )}
                          <button className="enlace" disabled={ocupado !== null} onClick={() => quitarContacto(c)}>
                            Quitar
                          </button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {editar && (
                <form className="formulario formulario-compacto" onSubmit={agregarContacto}>
                  <div className="fila-doble">
                    <label>
                      Nombre
                      <input value={contacto.nombre} required maxLength={150} onChange={(e) => setContacto({ ...contacto, nombre: e.target.value })} />
                    </label>
                    <label>
                      Cargo
                      <input value={contacto.cargo} maxLength={100} onChange={(e) => setContacto({ ...contacto, cargo: e.target.value })} />
                    </label>
                  </div>
                  <div className="fila-doble">
                    <label>
                      Correo
                      <input type="email" value={contacto.correo} maxLength={200} onChange={(e) => setContacto({ ...contacto, correo: e.target.value })} />
                    </label>
                    <label>
                      Teléfono
                      <input value={contacto.telefono} maxLength={40} onChange={(e) => setContacto({ ...contacto, telefono: e.target.value })} />
                    </label>
                  </div>
                  <div>
                    <BotonAccion primario={false} ocupado={ocupado === "contacto"} textoOcupado="Agregando…">
                      Agregar contacto
                    </BotonAccion>
                  </div>
                </form>
              )}
            </section>

            <section className="subseccion">
              <h3>Cuentas bancarias</h3>
              {!banco && (
                <p className="tenue">
                  Ves las cuentas enmascaradas. Solo quien tiene el permiso de cuentas bancarias puede verlas completas, registrarlas o
                  cambiarlas.
                </p>
              )}
              {ficha.cuentas.length === 0 ? (
                <p className="tenue">Sin cuentas registradas.</p>
              ) : (
                <ul className="lista-simple">
                  {ficha.cuentas.map((c) => (
                    <li key={c.id} className={c.activo ? undefined : "inactiva"}>
                      <div>
                        <p className="fuerte">
                          {c.banco} · {NOMBRE_TIPO_CUENTA[c.tipo] ?? c.tipo} · {c.moneda}
                        </p>
                        <p className="tenue">
                          N.° {c.numero}
                          {c.cci && ` · CCI ${c.cci}`}
                          {c.swift && ` · SWIFT ${c.swift}`}
                        </p>
                      </div>
                      {banco ? (
                        <BotonAccion
                          primario={false}
                          className="boton-chico"
                          ocupado={ocupado === `cuenta-${c.id}`}
                          textoOcupado="…"
                          onClick={() => cambiarCuenta(c.id, !c.activo)}
                        >
                          {c.activo ? "Desactivar" : "Reactivar"}
                        </BotonAccion>
                      ) : (
                        <Estado activo={c.activo} si="Activa" no="Inactiva" />
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {banco && (
                <form className="formulario formulario-compacto" onSubmit={agregarCuenta}>
                  <div className="fila-doble">
                    <label>
                      Banco
                      <input value={cuenta.banco} required maxLength={100} placeholder="BCP" onChange={(e) => setCuenta({ ...cuenta, banco: e.target.value })} />
                    </label>
                    <label>
                      Tipo
                      <select value={cuenta.tipo} onChange={(e) => setCuenta({ ...cuenta, tipo: e.target.value })}>
                        {Object.entries(NOMBRE_TIPO_CUENTA).map(([k, v]) => (
                          <option key={k} value={k}>
                            {v}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <div className="fila-doble">
                    <label>
                      Moneda
                      <select value={cuenta.moneda} onChange={(e) => setCuenta({ ...cuenta, moneda: e.target.value })}>
                        {monedasActivas.map((m) => (
                          <option key={m.codigo} value={m.codigo}>
                            {m.codigo}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Número de cuenta
                      <input value={cuenta.numero} required maxLength={40} onChange={(e) => setCuenta({ ...cuenta, numero: e.target.value })} />
                    </label>
                  </div>
                  {local ? (
                    <label>
                      CCI (20 dígitos)
                      <input value={cuenta.cci} required inputMode="numeric" maxLength={24} onChange={(e) => setCuenta({ ...cuenta, cci: e.target.value })} />
                    </label>
                  ) : (
                    <label>
                      SWIFT / BIC
                      <input value={cuenta.swift} required maxLength={11} onChange={(e) => setCuenta({ ...cuenta, swift: e.target.value.toUpperCase() })} />
                    </label>
                  )}
                  <small className="tenue">Las cuentas no se editan: para cambiar una, desactívala y registra la nueva. Todo queda en la auditoría.</small>
                  <div>
                    <BotonAccion primario={false} ocupado={ocupado === "cuenta"} textoOcupado="Registrando…">
                      Registrar cuenta
                    </BotonAccion>
                  </div>
                </form>
              )}
            </section>

            {categorias.length > 0 && (
              <section className="subseccion">
                <h3>Categorías que provee</h3>
                <p className="tenue">Sirven para sugerir este proveedor al comprar artículos de esas categorías.</p>
                <div className="lista-checks">
                  {catsOrdenadas.map((c) => (
                    <label key={c.id} className="opcion" style={{ paddingLeft: (c.nivel - 1) * 20 }}>
                      <input
                        type="checkbox"
                        checked={cats.has(c.id)}
                        disabled={!editar}
                        onChange={(e) => {
                          const n = new Set(cats);
                          if (e.target.checked) n.add(c.id);
                          else n.delete(c.id);
                          setCats(n);
                        }}
                      />
                      <span>
                        {c.codigo} · {c.nombre}
                      </span>
                    </label>
                  ))}
                </div>
                {editar && (
                  <div>
                    <BotonAccion primario={false} ocupado={ocupado === "categorias"} disabled={catsSinCambios} onClick={guardarCategorias}>
                      Guardar categorías
                    </BotonAccion>
                  </div>
                )}
              </section>
            )}

            {empresas.length > 0 && (
              <section className="subseccion">
                <h3>Empresas</h3>
                <p className="tenue">Una empresa bloqueada no podrá emitir órdenes de compra a este proveedor.</p>
                <ul className="lista-simple">
                  {empresas.map((em) => {
                    const bloqueo = ficha.bloqueos.find((b) => b.empresa_id === em.id);
                    return (
                      <li key={em.id} className="li-bloqueo">
                        <div>
                          <p className="fuerte">{em.razon_social}</p>
                          {bloqueo ? <p className="texto-alerta">Bloqueado: {bloqueo.motivo}</p> : <p className="tenue">Habilitado</p>}
                          {editar && !bloqueo && (
                            <input
                              className="input-motivo"
                              placeholder="Motivo del bloqueo"
                              maxLength={300}
                              value={motivos[em.id] ?? ""}
                              onChange={(e) => setMotivos({ ...motivos, [em.id]: e.target.value })}
                            />
                          )}
                        </div>
                        {editar && (
                          <BotonAccion
                            primario={false}
                            className="boton-chico"
                            ocupado={ocupado === `bloqueo-${em.id}`}
                            textoOcupado="…"
                            disabled={!bloqueo && !(motivos[em.id] ?? "").trim()}
                            onClick={() => bloquear(em, !bloqueo)}
                          >
                            {bloqueo ? "Habilitar" : "Bloquear"}
                          </BotonAccion>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}
          </>
        )}
      </Panel>
    </>
  );
}
