import { FileSpreadsheet } from "lucide-react";
import { useEffect, useState } from "react";
import { api, descargar, type OpcionesCompra } from "../api";
import { BotonAccion, Encabezado, MensajeError } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva } from "../empresa";

/** Reporte Excel de solicitudes y órdenes de compra, con filtros. */
export default function ReporteCompras() {
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [op, setOp] = useState<OpcionesCompra | null>(null);
  const [f, setF] = useState({ desde: "", hasta: "", estado: "", proveedor_id: "", unidad_negocio_id: "", incluir_sin_orden: true });
  const [error, setError] = useState<unknown>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    if (!empresa) return;
    api<OpcionesCompra>(`/compras/empresas/${empresa.id}/opciones`)
      .then(setOp)
      .catch(() => setOp(null));
  }, [empresa]);

  const generar = async () => {
    if (!empresa) return;
    setOcupado(true);
    setError(null);
    try {
      const q = new URLSearchParams();
      for (const [k, v] of Object.entries(f)) if (v !== "" && v !== true) q.set(k, String(v));
      await descargar(`/compras/empresas/${empresa.id}/reporte?${q}`, `compras-${new Date().toISOString().slice(0, 10)}.xlsx`);
    } catch (e) {
      setError(e);
    } finally {
      setOcupado(false);
    }
  };

  return (
    <>
      <Encabezado
        titulo="Reporte de compras"
        descripcion="Excel con una fila por línea de orden y su solicitud de origen. Incluye, si quieres, las solicitudes que aún no tienen orden."
      />
      <div className="barra-filtros">
        <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={elegir} />
      </div>
      {!empresa ? (
        <SinEmpresa cargando={cargando} />
      ) : (
        <div className="formulario" style={{ maxWidth: 720 }}>
          <div className="fila-formulario">
            <label>
              Desde
              <input type="date" value={f.desde} onChange={(e) => setF({ ...f, desde: e.target.value })} />
            </label>
            <label>
              Hasta
              <input type="date" value={f.hasta} onChange={(e) => setF({ ...f, hasta: e.target.value })} />
            </label>
            <label>
              Estado de la orden
              <select value={f.estado} onChange={(e) => setF({ ...f, estado: e.target.value })}>
                <option value="">Todos</option>
                {op?.estados.map((e) => (
                  <option key={e.codigo} value={e.codigo}>
                    {e.nombre}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="fila-formulario">
            <label>
              Proveedor
              <select value={f.proveedor_id} onChange={(e) => setF({ ...f, proveedor_id: e.target.value })}>
                <option value="">Todos</option>
                {op?.proveedores.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.razon_social}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Unidad de negocio
              <select value={f.unidad_negocio_id} onChange={(e) => setF({ ...f, unidad_negocio_id: e.target.value })}>
                <option value="">Todas</option>
                {op?.unidades.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nombre}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="opcion">
            <input type="checkbox" checked={f.incluir_sin_orden} onChange={(e) => setF({ ...f, incluir_sin_orden: e.target.checked })} />
            <span>Incluir solicitudes que aún no tienen orden (no se filtran por estado ni proveedor)</span>
          </label>
          <MensajeError error={error} />
          <div className="acciones">
            <BotonAccion ocupado={ocupado} textoOcupado="Generando…" onClick={generar}>
              <FileSpreadsheet size={16} aria-hidden="true" /> Descargar Excel
            </BotonAccion>
          </div>
        </div>
      )}
    </>
  );
}
