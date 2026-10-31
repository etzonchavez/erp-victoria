import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, cuentaTexto, decimal, type Cuenta, type Impuesto } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva } from "../empresa";
import { useSesion } from "../sesion";

type Formulario = { codigo: string; nombre: string; tasa: string; cuenta_id: string; activo: boolean };

export default function Impuestos() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const editar = puede("contabilidad.impuesto.editar");
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [impuestos, setImpuestos] = useState<Impuesto[]>([]);
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<Impuesto | "nuevo" | null>(null);
  const [form, setForm] = useState<Formulario>({ codigo: "", nombre: "", tasa: "", cuenta_id: "", activo: true });
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    if (!empresa) return;
    setError(null);
    try {
      const [i, c] = await Promise.all([
        api<Impuesto[]>(`/contabilidad/empresas/${empresa.id}/impuestos`),
        puede("contabilidad.cuenta.ver") ? api<Cuenta[]>(`/contabilidad/empresas/${empresa.id}/cuentas`) : Promise.resolve([]),
      ]);
      setImpuestos(i);
      setCuentas(c);
    } catch (e) {
      setError(e);
    }
  }, [empresa, puede]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const abrir = (i: Impuesto | "nuevo") => {
    setErrorForm(null);
    setEditando(i);
    setForm(
      i === "nuevo"
        ? { codigo: "", nombre: "", tasa: "", cuenta_id: "", activo: true }
        : { codigo: i.codigo, nombre: i.nombre, tasa: decimal(i.tasa), cuenta_id: i.cuenta?.id ?? "", activo: i.activo },
    );
  };
  const cerrar = useCallback(() => setEditando(null), []);
  const nuevo = editando === "nuevo";
  const conTasa = Number(form.tasa) > 0;

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    if (!empresa) return;
    setGuardando(true);
    setErrorForm(null);
    const cuerpo = { nombre: form.nombre, tasa: form.tasa, cuenta_id: form.cuenta_id || null };
    try {
      if (nuevo) {
        await api(`/contabilidad/empresas/${empresa.id}/impuestos`, { metodo: "POST", cuerpo: { ...cuerpo, codigo: form.codigo } });
        avisar(`Impuesto ${form.codigo.toUpperCase()} creado.`);
      } else if (editando) {
        await api(`/contabilidad/impuestos/${editando.id}`, { metodo: "PATCH", cuerpo: { ...cuerpo, activo: form.activo } });
        avisar(`Impuesto ${editando.codigo} guardado.`);
      }
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const opciones = cuentas.filter((c) => c.imputable && c.activo && (c.naturaleza === "pasivo" || c.naturaleza === "activo"));

  return (
    <>
      <Encabezado
        titulo="Impuestos"
        descripcion="Impuestos que se aplican a las compras y la cuenta donde se registran. Los artículos usan IGV 18 % por defecto."
        accion={
          editar && (
            <button className="boton boton-primario" onClick={() => abrir("nuevo")} disabled={!empresa}>
              Crear impuesto
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
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Código</th>
                <th>Nombre</th>
                <th className="numero">Tasa</th>
                <th>Cuenta</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {impuestos.map((i) => (
                <tr key={i.id} onClick={() => abrir(i)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrir(i)}>
                  <td className="fuerte">{i.codigo}</td>
                  <td>{i.nombre}</td>
                  <td className="numero">{decimal(i.tasa)} %</td>
                  <td>{cuentaTexto(i.cuenta)}</td>
                  <td>
                    <Estado activo={i.activo} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel titulo={nuevo ? "Crear impuesto" : `Impuesto ${form.codigo}`} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          <label>
            Código
            <input
              value={form.codigo}
              maxLength={20}
              required
              disabled={!nuevo}
              placeholder="IVAP"
              onChange={(e) => setForm({ ...form, codigo: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "") })}
            />
          </label>
          <label>
            Nombre
            <input value={form.nombre} maxLength={100} required disabled={!editar} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </label>
          <label>
            Tasa (%)
            <input
              type="number"
              inputMode="decimal"
              min={0}
              max={100}
              step="0.0001"
              required
              disabled={!editar}
              value={form.tasa}
              onChange={(e) => setForm({ ...form, tasa: e.target.value })}
            />
            <small>0 para exonerado o inafecto.</small>
          </label>
          <label>
            Cuenta
            <select value={form.cuenta_id} required={conTasa} disabled={!editar} onChange={(e) => setForm({ ...form, cuenta_id: e.target.value })}>
              <option value="">{conTasa ? "Elegir cuenta…" : "Sin cuenta"}</option>
              {opciones.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.codigo} {c.nombre}
                </option>
              ))}
            </select>
          </label>
          {!nuevo && (
            <label className="opcion">
              <input type="checkbox" checked={form.activo} disabled={!editar} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
              <span>Impuesto activo</span>
            </label>
          )}
          <MensajeError error={errorForm} />
          {editar && (
            <div className="acciones">
              <button type="button" className="boton" onClick={cerrar}>
                Cancelar
              </button>
              <BotonAccion ocupado={guardando} textoOcupado={nuevo ? "Creando…" : "Guardando…"}>
                {nuevo ? "Crear impuesto" : "Guardar cambios"}
              </BotonAccion>
            </div>
          )}
        </form>
      </Panel>
    </>
  );
}
