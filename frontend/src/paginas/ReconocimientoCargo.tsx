import { useCallback, useEffect, useState } from "react";
import { api, type Cuenta } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, MensajeError } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva } from "../empresa";
import { useSesion } from "../sesion";

type Config = {
  momentos: { tipo_articulo: string; nombre: string; momento: string }[];
  opciones: { codigo: string; nombre: string }[];
  cuenta_recepcion_id: string | null;
  cuenta_recepcion: string | null;
};

const EXPLICACION: Record<string, string> = {
  recepcion: "Al recibir: Debe gasto o existencia · Haber cuenta puente. Al facturar: Debe cuenta puente + IGV · Haber proveedor.",
  facturacion: "Al facturar: Debe gasto o existencia + IGV · Haber proveedor. Al recibir no hay asiento.",
};

/** Cuentas por pagar: cuándo se reconoce el cargo de las compras, por tipo de artículo. */
export default function ReconocimientoCargo() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const editar = puede("contabilidad.cxp.editar");
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [config, setConfig] = useState<Config | null>(null);
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    if (!empresa) return;
    setError(null);
    try {
      setConfig(await api<Config>(`/contabilidad/empresas/${empresa.id}/reconocimiento`));
      if (editar) setCuentas(await api<Cuenta[]>(`/contabilidad/empresas/${empresa.id}/cuentas`).catch(() => []));
    } catch (e) {
      setError(e);
    }
  }, [empresa, editar]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const guardar = async () => {
    if (!empresa || !config) return;
    setGuardando(true);
    setError(null);
    try {
      setConfig(
        await api<Config>(`/contabilidad/empresas/${empresa.id}/reconocimiento`, {
          metodo: "PUT",
          cuerpo: {
            momentos: Object.fromEntries(config.momentos.map((m) => [m.tipo_articulo, m.momento])),
            cuenta_recepcion_id: config.cuenta_recepcion_id,
          },
        }),
      );
      avisar("Reconocimiento del cargo guardado.");
    } catch (e) {
      setError(e);
    } finally {
      setGuardando(false);
    }
  };
  const pasivos = cuentas.filter((c) => c.imputable && c.activo && c.codigo.startsWith("42"));

  return (
    <>
      <Encabezado
        titulo="Reconocimiento del cargo"
        descripcion="Cuándo se registra el gasto o la existencia de cada compra: al recibir la mercadería o el servicio, o al registrar la factura. Se aplica por tipo de artículo en cada empresa."
        accion={
          editar && (
            <BotonAccion ocupado={guardando} textoOcupado="Guardando…" onClick={guardar} disabled={!config}>
              Guardar
            </BotonAccion>
          )
        }
      />
      <div className="barra-filtros">
        <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={elegir} />
      </div>
      <MensajeError error={error} />
      {!empresa ? (
        <SinEmpresa cargando={cargando} />
      ) : (
        config && (
          <div className="formulario" style={{ maxWidth: 820 }}>
            <div className="tabla-contenedor">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Tipo de artículo</th>
                    <th>Se reconoce</th>
                    <th>Asientos</th>
                  </tr>
                </thead>
                <tbody>
                  {config.momentos.map((m) => (
                    <tr key={m.tipo_articulo}>
                      <td className="fuerte">{m.nombre}</td>
                      <td>
                        <select
                          aria-label={`Momento para ${m.nombre}`}
                          value={m.momento}
                          disabled={!editar}
                          onChange={(e) =>
                            setConfig({
                              ...config,
                              momentos: config.momentos.map((x) => (x.tipo_articulo === m.tipo_articulo ? { ...x, momento: e.target.value } : x)),
                            })
                          }
                        >
                          {config.opciones.map((o) => (
                            <option key={o.codigo} value={o.codigo}>
                              {o.nombre}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="tenue">{EXPLICACION[m.momento]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <label>
              Cuenta puente de recepción (facturas por recibir)
              {editar ? (
                <select value={config.cuenta_recepcion_id ?? ""} onChange={(e) => setConfig({ ...config, cuenta_recepcion_id: e.target.value || null })}>
                  <option value="">Sin cuenta</option>
                  {pasivos.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.codigo} · {c.nombre}
                    </option>
                  ))}
                </select>
              ) : (
                <input value={config.cuenta_recepcion ?? "Sin cuenta"} disabled />
              )}
              <small>En el PCGE es la 4211 «Facturas no emitidas». La cuenta del proveedor al facturar (4212 «Emitidas») sale del perfil contable de cada artículo.</small>
            </label>
          </div>
        )
      )}
    </>
  );
}
