import { useCallback, useEffect, useRef, useState } from "react";
import { api, archivoUrl, type ConfigFormato, type FormatoOC } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, MensajeError } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva } from "../empresa";

/** Formato PDF de la orden de compra: uno por empresa, con vista previa en vivo. */
export default function FormatoOrden() {
  const { avisar } = useAvisos();
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [formato, setFormato] = useState<FormatoOC | null>(null);
  const [config, setConfig] = useState<ConfigFormato | null>(null);
  const [vista, setVista] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const temporizador = useRef<number | undefined>(undefined);

  const cargar = useCallback(async () => {
    if (!empresa) return;
    setError(null);
    try {
      const f = await api<FormatoOC>(`/compras/empresas/${empresa.id}/formato`);
      setFormato(f);
      setConfig(f.configuracion);
    } catch (e) {
      setError(e);
    }
  }, [empresa]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  // Vista previa: se regenera al dejar de escribir
  useEffect(() => {
    if (!empresa || !config) return;
    window.clearTimeout(temporizador.current);
    temporizador.current = window.setTimeout(() => {
      archivoUrl(`/compras/empresas/${empresa.id}/formato/vista-previa`, { metodo: "POST", cuerpo: { configuracion: config } })
        .then((url) =>
          setVista((anterior) => {
            if (anterior) URL.revokeObjectURL(anterior);
            return url;
          }),
        )
        .catch(setError);
    }, 700);
    return () => window.clearTimeout(temporizador.current);
  }, [config, empresa, formato?.tiene_logo]);

  if (!empresa)
    return (
      <>
        <Encabezado titulo="Formato de la orden de compra" descripcion="Cómo se ve el PDF que recibe el proveedor." />
        <SinEmpresa cargando={cargando} />
      </>
    );

  const cambiar = (c: Partial<ConfigFormato>) => config && setConfig({ ...config, ...c });
  const mover = (i: number, d: -1 | 1) => {
    if (!config) return;
    const s = [...config.secciones];
    const j = i + d;
    if (j < 0 || j >= s.length) return;
    [s[i], s[j]] = [s[j], s[i]];
    cambiar({ secciones: s });
  };
  const nombreSeccion = (c: string) => formato?.secciones.find((s) => s.codigo === c)?.nombre ?? c;

  const guardar = async () => {
    if (!config) return;
    setGuardando(true);
    setError(null);
    try {
      const f = await api<FormatoOC>(`/compras/empresas/${empresa.id}/formato`, { metodo: "PUT", cuerpo: { configuracion: config } });
      setFormato(f);
      setConfig(f.configuracion);
      avisar("Formato de la orden de compra guardado.");
    } catch (e) {
      setError(e);
    } finally {
      setGuardando(false);
    }
  };
  const subirLogo = async (archivo: File | undefined) => {
    if (!archivo) return;
    setSubiendo(true);
    setError(null);
    try {
      setFormato(await api<FormatoOC>(`/compras/empresas/${empresa.id}/formato/logo`, { metodo: "POST", archivo: { campo: "archivo", valor: archivo } }));
      avisar("Logo del formato actualizado.");
    } catch (e) {
      setError(e);
    } finally {
      setSubiendo(false);
    }
  };
  const quitarLogo = async () => {
    try {
      setFormato(await api<FormatoOC>(`/compras/empresas/${empresa.id}/formato/logo`, { metodo: "DELETE" }));
      avisar("Se usará el logo general del ERP.");
    } catch (e) {
      setError(e);
    }
  };

  return (
    <>
      <Encabezado
        titulo="Formato de la orden de compra"
        descripcion="Cómo se ve el PDF que recibe el proveedor: logo, color, qué datos se imprimen y en qué orden. Es uno por empresa."
        accion={
          <BotonAccion ocupado={guardando} textoOcupado="Guardando…" onClick={guardar} disabled={!config}>
            Guardar formato
          </BotonAccion>
        }
      />
      <div className="barra-filtros">
        <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={elegir} />
      </div>
      <MensajeError error={error} />
      {config && formato && (
        <div className="formato-oc">
          <div className="formulario">
            <div className="fila-formulario">
              <label style={{ flexGrow: 3 }}>
                Título
                <input value={config.titulo} maxLength={60} onChange={(e) => cambiar({ titulo: e.target.value })} />
              </label>
              <label>
                Color
                <input type="color" value={config.color} onChange={(e) => cambiar({ color: e.target.value })} />
              </label>
            </div>
            <div className="fila-formulario">
              <label>
                Tamaño de página
                <select value={config.tamano} onChange={(e) => cambiar({ tamano: e.target.value })}>
                  <option value="A4">A4</option>
                  <option value="carta">Carta</option>
                </select>
              </label>
              <label>
                Datos por fila
                <select value={config.columnas_datos} onChange={(e) => cambiar({ columnas_datos: Number(e.target.value) })}>
                  <option value={1}>1 bloque</option>
                  <option value={2}>2 bloques</option>
                  <option value={3}>3 bloques</option>
                </select>
              </label>
            </div>

            <fieldset>
              <legend>Logo</legend>
              <label className="opcion">
                <input type="checkbox" checked={config.mostrar_logo} onChange={(e) => cambiar({ mostrar_logo: e.target.checked })} />
                <span>Imprimir el logo</span>
              </label>
              <small>{formato.tiene_logo ? "Este formato tiene su propio logo." : "Se usa el logo general del ERP (Administración › Personalización)."}</small>
              <div className="acciones-linea">
                <label className="boton boton-chico">
                  {subiendo ? "Subiendo…" : "Subir logo de la empresa"}
                  <input type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(e) => subirLogo(e.target.files?.[0])} />
                </label>
                {formato.tiene_logo && (
                  <button type="button" className="boton boton-chico" onClick={quitarLogo}>
                    Quitar logo propio
                  </button>
                )}
              </div>
            </fieldset>

            <fieldset>
              <legend>Secciones y orden</legend>
              <ul className="lista-orden">
                {config.secciones.map((s, i) => (
                  <li key={s.codigo}>
                    <label className="opcion">
                      <input
                        type="checkbox"
                        checked={s.activo}
                        onChange={(e) => cambiar({ secciones: config.secciones.map((x) => (x.codigo === s.codigo ? { ...x, activo: e.target.checked } : x)) })}
                      />
                      <span>{nombreSeccion(s.codigo)}</span>
                    </label>
                    <span className="acciones-linea">
                      <button type="button" className="boton boton-chico" aria-label={`Subir ${nombreSeccion(s.codigo)}`} disabled={i === 0} onClick={() => mover(i, -1)}>
                        ↑
                      </button>
                      <button type="button" className="boton boton-chico" aria-label={`Bajar ${nombreSeccion(s.codigo)}`} disabled={i === config.secciones.length - 1} onClick={() => mover(i, 1)}>
                        ↓
                      </button>
                    </span>
                  </li>
                ))}
              </ul>
              <small>Proveedor, entrega, condiciones y datos adicionales seguidos se agrupan en bloques lado a lado.</small>
            </fieldset>

            <fieldset>
              <legend>Columnas del detalle</legend>
              <div className="columnas-check">
                {formato.columnas.map((c) => (
                  <label key={c.codigo} className="opcion">
                    <input
                      type="checkbox"
                      checked={config.columnas.includes(c.codigo)}
                      disabled={c.codigo === "descripcion"}
                      onChange={(e) =>
                        cambiar({
                          columnas: formato.columnas.map((x) => x.codigo).filter((x) => (x === c.codigo ? e.target.checked : config.columnas.includes(x))),
                        })
                      }
                    />
                    <span>{c.nombre}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <label>
              Términos y condiciones
              <textarea rows={5} maxLength={4000} value={config.terminos} onChange={(e) => cambiar({ terminos: e.target.value })} />
            </label>
            <label>
              <span>
                Pie de página <span className="tenue">(opcional)</span>
              </span>
              <input value={config.pie} maxLength={200} placeholder="Av. … · Central 01 555 0000 · compras@empresa.pe" onChange={(e) => cambiar({ pie: e.target.value })} />
            </label>
          </div>
          <div className="vista-pdf">
            {vista ? <iframe title="Vista previa del PDF" src={vista} /> : <p className="tenue">Generando vista previa…</p>}
          </div>
        </div>
      )}
    </>
  );
}
