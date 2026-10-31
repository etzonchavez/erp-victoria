import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, NOMBRE_NATURALEZA, type Cuenta } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva } from "../empresa";
import { useSesion } from "../sesion";

type Formulario = { codigo: string; nombre: string; naturaleza: string; activo: boolean };

export default function PlanCuentas() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const editar = puede("contabilidad.cuenta.editar");
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [buscar, setBuscar] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<Cuenta | "nueva" | null>(null);
  const [form, setForm] = useState<Formulario>({ codigo: "", nombre: "", naturaleza: "", activo: true });
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);
  const [cargandoPlantilla, setCargandoPlantilla] = useState(false);

  const cargar = useCallback(async () => {
    if (!empresa) return;
    setError(null);
    try {
      setCuentas(await api<Cuenta[]>(`/contabilidad/empresas/${empresa.id}/cuentas`));
    } catch (e) {
      setError(e);
    }
  }, [empresa]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const porCodigo = useMemo(() => new Map(cuentas.map((c) => [c.codigo, c])), [cuentas]);
  const texto = buscar.trim().toLowerCase();
  const visibles = texto
    ? cuentas.filter((c) => c.codigo.startsWith(texto) || c.nombre.toLowerCase().includes(texto))
    : cuentas;

  // Padre que tendrá la cuenta nueva: la existente de código más largo que sea su prefijo.
  const padreNueva = useMemo(() => {
    for (let n = form.codigo.length - 1; n > 0; n--) {
      const p = porCodigo.get(form.codigo.slice(0, n));
      if (p) return p;
    }
    return null;
  }, [form.codigo, porCodigo]);

  const abrir = (c: Cuenta | "nueva") => {
    setErrorForm(null);
    setEditando(c);
    setForm(c === "nueva" ? { codigo: "", nombre: "", naturaleza: "", activo: true } : { ...c });
  };
  const cerrar = useCallback(() => setEditando(null), []);
  const nueva = editando === "nueva";

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    if (!empresa) return;
    setGuardando(true);
    setErrorForm(null);
    try {
      if (nueva) {
        await api(`/contabilidad/empresas/${empresa.id}/cuentas`, {
          metodo: "POST",
          cuerpo: { codigo: form.codigo, nombre: form.nombre, naturaleza: form.naturaleza || null },
        });
        avisar(`Cuenta ${form.codigo} creada.`);
      } else if (editando) {
        await api(`/contabilidad/cuentas/${editando.id}`, {
          metodo: "PATCH",
          cuerpo: { nombre: form.nombre, activo: form.activo },
        });
        avisar(`Cuenta ${editando.codigo} guardada.`);
      }
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const cargarPlantilla = async () => {
    if (!empresa) return;
    setCargandoPlantilla(true);
    setError(null);
    try {
      const r = await api<{ cuentas: number }>(`/contabilidad/empresas/${empresa.id}/plantilla`, { metodo: "POST" });
      avisar(`Plantilla cargada: ${r.cuentas} cuentas, perfiles contables e impuestos.`);
      await cargar();
    } catch (err) {
      setError(err);
    } finally {
      setCargandoPlantilla(false);
    }
  };

  return (
    <>
      <Encabezado
        titulo="Plan de cuentas"
        descripcion="Cuentas contables de la empresa. Solo las cuentas del último nivel (imputables) se usan en perfiles, impuestos y compras."
        accion={
          editar &&
          cuentas.length > 0 && (
            <button className="boton boton-primario" onClick={() => abrir("nueva")}>
              Agregar cuenta
            </button>
          )
        }
      />
      <div className="barra-filtros">
        <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={elegir} />
        {cuentas.length > 0 && (
          <label className="filtro">
            Buscar
            <input value={buscar} placeholder="Código o nombre" onChange={(e) => setBuscar(e.target.value)} />
          </label>
        )}
      </div>
      <MensajeError error={error} />
      {!empresa ? (
        <SinEmpresa cargando={cargando} />
      ) : cuentas.length === 0 ? (
        <div className="vacio">
          <p>Esta empresa aún no tiene plan de cuentas.</p>
          {editar && (
            <p style={{ marginTop: 12 }}>
              <BotonAccion ocupado={cargandoPlantilla} textoOcupado="Cargando plantilla…" onClick={cargarPlantilla}>
                Cargar plantilla del país (PCGE)
              </BotonAccion>
            </p>
          )}
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla tabla-plan">
            <thead>
              <tr>
                <th>Cuenta</th>
                <th>Naturaleza</th>
                <th>Uso</th>
                <th>Origen</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {visibles.map((c) => (
                <tr
                  key={c.id}
                  className={c.nivel === 1 ? "fila-titulo" : undefined}
                  onClick={() => abrir(c)}
                  tabIndex={0}
                  onKeyDown={(k) => k.key === "Enter" && abrir(c)}
                >
                  <td style={{ paddingLeft: 16 + (texto ? 0 : (c.nivel - 1) * 20) }}>
                    <span className="codigo-cuenta">{c.codigo}</span> {c.nombre}
                  </td>
                  <td>{NOMBRE_NATURALEZA[c.naturaleza] ?? c.naturaleza}</td>
                  <td>{c.imputable ? <span className="etiqueta etiqueta-estandar">Imputable</span> : <span className="tenue">Agrupa</span>}</td>
                  <td className="tenue">{c.plantilla === "propia" ? "Propia" : c.plantilla}</td>
                  <td>
                    <Estado activo={c.activo} si="Activa" no="Inactiva" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel titulo={nueva ? "Agregar cuenta" : `Cuenta ${form.codigo}`} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          <label>
            Código
            <input
              value={form.codigo}
              inputMode="numeric"
              maxLength={20}
              required
              disabled={!nueva}
              placeholder="63211"
              onChange={(e) => setForm({ ...form, codigo: e.target.value.replace(/\D/g, "") })}
            />
            {nueva && form.codigo && (
              <small>
                {padreNueva
                  ? `Será subcuenta de ${padreNueva.codigo} ${padreNueva.nombre} (${NOMBRE_NATURALEZA[padreNueva.naturaleza]?.toLowerCase()}).`
                  : "Cuenta de primer nivel."}
              </small>
            )}
          </label>
          <label>
            Nombre
            <input value={form.nombre} maxLength={200} required disabled={!editar} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </label>
          {nueva && form.codigo && !padreNueva && (
            <label>
              Naturaleza
              <select value={form.naturaleza} onChange={(e) => setForm({ ...form, naturaleza: e.target.value })}>
                <option value="">Según el elemento del PCGE</option>
                {Object.entries(NOMBRE_NATURALEZA).map(([k, v]) => (
                  <option key={k} value={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          )}
          {!nueva && editando && (
            <>
              <p className="tenue">
                {NOMBRE_NATURALEZA[editando.naturaleza]} · nivel {editando.nivel} ·{" "}
                {editando.imputable ? "imputable (último nivel)" : "agrupa subcuentas"}
              </p>
              <label className="opcion">
                <input type="checkbox" checked={form.activo} disabled={!editar} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
                <span>
                  Cuenta activa
                  <small>No se desactiva si la usa un perfil o impuesto, o si tiene subcuentas activas.</small>
                </span>
              </label>
            </>
          )}
          <MensajeError error={errorForm} />
          {editar && (
            <div className="acciones">
              <button type="button" className="boton" onClick={cerrar}>
                Cancelar
              </button>
              <BotonAccion ocupado={guardando} textoOcupado={nueva ? "Creando…" : "Guardando…"}>
                {nueva ? "Agregar cuenta" : "Guardar cambios"}
              </BotonAccion>
            </div>
          )}
        </form>
      </Panel>
    </>
  );
}
