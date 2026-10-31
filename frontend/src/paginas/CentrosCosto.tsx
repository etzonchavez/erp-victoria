import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type CentroCosto } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva } from "../empresa";
import { useSesion } from "../sesion";

type Formulario = { codigo: string; nombre: string; unidad_negocio_id: string; responsable: string; activo: boolean };

export default function CentrosCosto() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const editar = puede("contabilidad.centro_costo.editar");
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [centros, setCentros] = useState<CentroCosto[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<CentroCosto | "nuevo" | null>(null);
  const [form, setForm] = useState<Formulario>({ codigo: "", nombre: "", unidad_negocio_id: "", responsable: "", activo: true });
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    if (!empresa) return;
    setError(null);
    try {
      setCentros(await api<CentroCosto[]>(`/contabilidad/empresas/${empresa.id}/centros-costo`));
    } catch (e) {
      setError(e);
    }
  }, [empresa]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const unidades = empresa?.unidades ?? [];
  const nombreUnidad = (id: string) => unidades.find((u) => u.id === id)?.nombre ?? "—";

  const abrir = (c: CentroCosto | "nuevo") => {
    setErrorForm(null);
    setEditando(c);
    setForm(
      c === "nuevo"
        ? { codigo: "", nombre: "", unidad_negocio_id: unidades.find((u) => u.activo)?.id ?? "", responsable: "", activo: true }
        : { ...c, responsable: c.responsable ?? "" },
    );
  };
  const cerrar = useCallback(() => setEditando(null), []);
  const nuevo = editando === "nuevo";

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    if (!empresa) return;
    setGuardando(true);
    setErrorForm(null);
    try {
      if (nuevo) {
        await api(`/contabilidad/empresas/${empresa.id}/centros-costo`, {
          metodo: "POST",
          cuerpo: { codigo: form.codigo, nombre: form.nombre, unidad_negocio_id: form.unidad_negocio_id, responsable: form.responsable },
        });
        avisar(`Centro de costo ${form.codigo.toUpperCase()} creado.`);
      } else if (editando) {
        await api(`/contabilidad/centros-costo/${editando.id}`, {
          metodo: "PATCH",
          cuerpo: { nombre: form.nombre, unidad_negocio_id: form.unidad_negocio_id, responsable: form.responsable, activo: form.activo },
        });
        avisar(`Centro de costo ${editando.codigo} guardado.`);
      }
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <>
      <Encabezado
        titulo="Centros de costo"
        descripcion="Áreas que consumen las compras (administración, ventas, producción). Cada línea de una solicitud lleva su centro de costo para los reportes de gasto."
        accion={
          editar && (
            <button className="boton boton-primario" onClick={() => abrir("nuevo")} disabled={!empresa}>
              Crear centro de costo
            </button>
          )
        }
      />
      <div className="barra-filtros">
        <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={elegir} />
      </div>
      <MensajeError error={error} />
      {!empresa ? (
        <SinEmpresa cargando={cargando} />
      ) : centros.length === 0 ? (
        <div className="vacio">
          <p>Aún no hay centros de costo en esta empresa.</p>
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Código</th>
                <th>Nombre</th>
                <th>Unidad de negocio</th>
                <th>Responsable</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {centros.map((c) => (
                <tr key={c.id} onClick={() => abrir(c)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrir(c)}>
                  <td className="fuerte">{c.codigo}</td>
                  <td>{c.nombre}</td>
                  <td>{nombreUnidad(c.unidad_negocio_id)}</td>
                  <td>{c.responsable ?? <span className="tenue">—</span>}</td>
                  <td>
                    <Estado activo={c.activo} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel titulo={nuevo ? "Crear centro de costo" : `Centro de costo ${form.codigo}`} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          <label>
            Código
            <input
              value={form.codigo}
              maxLength={20}
              required
              disabled={!nuevo}
              placeholder="ADM-01"
              onChange={(e) => setForm({ ...form, codigo: e.target.value.toUpperCase() })}
            />
          </label>
          <label>
            Nombre
            <input value={form.nombre} maxLength={150} required disabled={!editar} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </label>
          <label>
            Unidad de negocio
            <select value={form.unidad_negocio_id} required disabled={!editar} onChange={(e) => setForm({ ...form, unidad_negocio_id: e.target.value })}>
              {unidades
                .filter((u) => u.activo || u.id === form.unidad_negocio_id)
                .map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nombre}
                  </option>
                ))}
            </select>
          </label>
          <label>
            <span>
              Responsable <span className="tenue">(opcional)</span>
            </span>
            <input value={form.responsable} maxLength={150} disabled={!editar} onChange={(e) => setForm({ ...form, responsable: e.target.value })} />
          </label>
          {!nuevo && (
            <label className="opcion">
              <input type="checkbox" checked={form.activo} disabled={!editar} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
              <span>Centro de costo activo</span>
            </label>
          )}
          <MensajeError error={errorForm} />
          {editar && (
            <div className="acciones">
              <button type="button" className="boton" onClick={cerrar}>
                Cancelar
              </button>
              <BotonAccion ocupado={guardando} textoOcupado={nuevo ? "Creando…" : "Guardando…"}>
                {nuevo ? "Crear centro de costo" : "Guardar cambios"}
              </BotonAccion>
            </div>
          )}
        </form>
      </Panel>
    </>
  );
}
