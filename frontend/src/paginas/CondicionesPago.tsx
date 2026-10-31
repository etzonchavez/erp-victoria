import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type CondicionPago } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { useSesion } from "../sesion";

type Formulario = { codigo: string; nombre: string; dias: number; activo: boolean };

export default function CondicionesPago() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const editar = puede("maestros.condicion_pago.editar");
  const [condiciones, setCondiciones] = useState<CondicionPago[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<CondicionPago | "nueva" | null>(null);
  const [form, setForm] = useState<Formulario>({ codigo: "", nombre: "", dias: 0, activo: true });
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setCondiciones(await api<CondicionPago[]>("/maestros/condiciones-pago"));
    } catch (e) {
      setError(e);
    }
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const abrir = (c: CondicionPago | "nueva") => {
    setErrorForm(null);
    setEditando(c);
    setForm(c === "nueva" ? { codigo: "", nombre: "", dias: 30, activo: true } : { ...c });
  };
  const cerrar = useCallback(() => setEditando(null), []);
  const nueva = editando === "nueva";

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setGuardando(true);
    setErrorForm(null);
    try {
      if (nueva) {
        await api("/maestros/condiciones-pago", { metodo: "POST", cuerpo: { codigo: form.codigo, nombre: form.nombre, dias: form.dias } });
        avisar(`Condición ${form.nombre} creada.`);
      } else if (editando) {
        await api(`/maestros/condiciones-pago/${editando.id}`, {
          metodo: "PATCH",
          cuerpo: { nombre: form.nombre, dias: form.dias, activo: form.activo },
        });
        avisar(`Condición ${form.nombre} guardada.`);
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
        titulo="Condiciones de pago"
        descripcion="Plazos de pago que se asignan a los proveedores. La orden de compra toma la condición del proveedor por defecto."
        accion={
          editar && (
            <button className="boton boton-primario" onClick={() => abrir("nueva")}>
              Crear condición
            </button>
          )
        }
      />
      <MensajeError error={error} />
      <div className="tabla-contenedor">
        <table className="tabla">
          <thead>
            <tr>
              <th>Código</th>
              <th>Nombre</th>
              <th className="numero">Días</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {condiciones.map((c) => (
              <tr key={c.id} onClick={() => abrir(c)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrir(c)}>
                <td className="fuerte">{c.codigo}</td>
                <td>{c.nombre}</td>
                <td className="numero">{c.dias}</td>
                <td>
                  <Estado activo={c.activo} si="Activa" no="Inactiva" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Panel titulo={nueva ? "Crear condición de pago" : `Condición ${form.codigo}`} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          <label>
            Código
            <input
              value={form.codigo}
              required
              maxLength={20}
              disabled={!nueva}
              placeholder="90D"
              onChange={(e) => setForm({ ...form, codigo: e.target.value.toUpperCase() })}
            />
          </label>
          <label>
            Nombre
            <input value={form.nombre} required maxLength={80} disabled={!editar} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </label>
          <label>
            Días de crédito
            <input type="number" min={0} max={365} value={form.dias} disabled={!editar} onChange={(e) => setForm({ ...form, dias: Number(e.target.value) })} />
            <small>0 = contado.</small>
          </label>
          {!nueva && (
            <label className="opcion">
              <input type="checkbox" checked={form.activo} disabled={!editar} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
              <span>
                Condición activa
                <small>No se desactiva mientras la use algún proveedor activo.</small>
              </span>
            </label>
          )}
          <MensajeError error={errorForm} />
          {editar && (
            <div className="acciones">
              <button type="button" className="boton" onClick={cerrar}>
                Cancelar
              </button>
              <BotonAccion ocupado={guardando} textoOcupado={nueva ? "Creando…" : "Guardando…"}>
                {nueva ? "Crear condición" : "Guardar cambios"}
              </BotonAccion>
            </div>
          )}
        </form>
      </Panel>
    </>
  );
}
