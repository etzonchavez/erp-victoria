import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, decimal, NOMBRE_TIPO_UNIDAD, type Conversion, type UnidadMedida } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { useSesion } from "../sesion";

type Formulario = { codigo: string; nombre: string; codigo_oficial: string; tipo: string; activo: boolean };
const VACIO: Formulario = { codigo: "", nombre: "", codigo_oficial: "", tipo: "cantidad", activo: true };

export default function Unidades() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const editar = puede("maestros.unidad.editar");
  const [unidades, setUnidades] = useState<UnidadMedida[]>([]);
  const [conversiones, setConversiones] = useState<Conversion[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<UnidadMedida | "nueva" | null>(null);
  const [form, setForm] = useState<Formulario>(VACIO);
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);
  const [conv, setConv] = useState({ origen: "", destino: "", factor: "" });
  const [errorConv, setErrorConv] = useState<unknown>(null);
  const [creandoConv, setCreandoConv] = useState(false);
  const [quitando, setQuitando] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      const [u, c] = await Promise.all([
        api<UnidadMedida[]>("/maestros/unidades-medida"),
        api<Conversion[]>("/maestros/conversiones"),
      ]);
      setUnidades(u);
      setConversiones(c);
    } catch (e) {
      setError(e);
    }
  }, []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const abrir = (u: UnidadMedida | "nueva") => {
    setErrorForm(null);
    setEditando(u);
    setForm(u === "nueva" ? VACIO : { ...u });
  };
  const cerrar = useCallback(() => setEditando(null), []);
  const nueva = editando === "nueva";

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setGuardando(true);
    setErrorForm(null);
    try {
      if (nueva) {
        await api("/maestros/unidades-medida", { metodo: "POST", cuerpo: form });
        avisar(`Unidad ${form.codigo} creada.`);
      } else if (editando) {
        const { nombre, codigo_oficial, tipo, activo } = form;
        await api(`/maestros/unidades-medida/${editando.codigo}`, {
          metodo: "PATCH",
          cuerpo: { nombre, codigo_oficial, tipo, activo },
        });
        avisar(`Unidad ${editando.codigo} guardada.`);
      }
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const crearConversion = async (e: FormEvent) => {
    e.preventDefault();
    setErrorConv(null);
    setCreandoConv(true);
    try {
      await api("/maestros/conversiones", { metodo: "POST", cuerpo: conv });
      avisar(`Conversión 1 ${conv.origen} = ${conv.factor} ${conv.destino} creada.`);
      setConv({ origen: "", destino: "", factor: "" });
      await cargar();
    } catch (err) {
      setErrorConv(err);
    } finally {
      setCreandoConv(false);
    }
  };

  const quitar = async (c: Conversion) => {
    setErrorConv(null);
    setQuitando(c.id);
    try {
      await api(`/maestros/conversiones/${c.id}`, { metodo: "DELETE" });
      avisar(`Conversión ${c.origen} → ${c.destino} eliminada.`);
      await cargar();
    } catch (err) {
      setErrorConv(err);
    } finally {
      setQuitando(null);
    }
  };

  const activas = unidades.filter((u) => u.activo);
  const tipoOrigen = unidades.find((u) => u.codigo === conv.origen)?.tipo;

  return (
    <>
      <Encabezado
        titulo="Unidades de medida"
        descripcion="Unidades que usan tus artículos. Cada una tiene su código oficial SUNAT (Catálogo N.° 03), que se usará en los comprobantes electrónicos."
        accion={
          editar && (
            <button className="boton boton-primario" onClick={() => abrir("nueva")}>
              Crear unidad
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
              <th>Código SUNAT</th>
              <th>Tipo</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {unidades.map((u) => (
              <tr key={u.codigo} onClick={() => abrir(u)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrir(u)}>
                <td className="fuerte">{u.codigo}</td>
                <td>{u.nombre}</td>
                <td>
                  <code>{u.codigo_oficial}</code>
                </td>
                <td>{NOMBRE_TIPO_UNIDAD[u.tipo] ?? u.tipo}</td>
                <td>
                  <Estado activo={u.activo} si="Activa" no="Inactiva" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="encabezado-seccion">
        <h2>Conversiones generales</h2>
      </div>
      <p className="tenue parrafo-seccion">
        Equivalencias que valen para todos los artículos (1 KG = 1000 G). Las propias de un artículo, como 1 CAJA = 12 UND, se
        definen en la ficha del artículo.
      </p>
      <ul className="lista-simple bloque-lista">
        {conversiones.map((c) => (
          <li key={c.id}>
            <p>
              1 <span className="fuerte">{c.origen}</span> = {decimal(c.factor)} <span className="fuerte">{c.destino}</span>
            </p>
            {editar && (
              <BotonAccion
                primario={false}
                className="boton-chico"
                ocupado={quitando === c.id}
                textoOcupado="Quitando…"
                onClick={() => quitar(c)}
              >
                Quitar
              </BotonAccion>
            )}
          </li>
        ))}
      </ul>
      {editar && (
        <form className="fila-formulario bloque" onSubmit={crearConversion}>
          <label>
            1 unidad de
            <select value={conv.origen} required onChange={(e) => setConv({ ...conv, origen: e.target.value, destino: "" })}>
              <option value="">Elegir…</option>
              {activas.map((u) => (
                <option key={u.codigo} value={u.codigo}>
                  {u.codigo} — {u.nombre}
                </option>
              ))}
            </select>
          </label>
          <label>
            equivale a
            <input
              type="number"
              inputMode="decimal"
              step="0.000001"
              min="0.000001"
              required
              value={conv.factor}
              onChange={(e) => setConv({ ...conv, factor: e.target.value })}
            />
          </label>
          <label>
            unidades de
            <select value={conv.destino} required disabled={!conv.origen} onChange={(e) => setConv({ ...conv, destino: e.target.value })}>
              <option value="">Elegir…</option>
              {activas
                .filter((u) => u.tipo === tipoOrigen && u.codigo !== conv.origen)
                .map((u) => (
                  <option key={u.codigo} value={u.codigo}>
                    {u.codigo} — {u.nombre}
                  </option>
                ))}
            </select>
          </label>
          <BotonAccion primario={false} ocupado={creandoConv} textoOcupado="Agregando…">
            Agregar conversión
          </BotonAccion>
        </form>
      )}
      <MensajeError error={errorConv} />

      <Panel titulo={nueva ? "Crear unidad" : `Unidad ${form.codigo}`} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          <label>
            Código interno
            <input
              value={form.codigo}
              maxLength={10}
              required
              disabled={!nueva}
              placeholder="BLS"
              onChange={(e) => setForm({ ...form, codigo: e.target.value.toUpperCase() })}
            />
            <small>Lo que verán los usuarios en solicitudes y órdenes.</small>
          </label>
          <label>
            Nombre
            <input value={form.nombre} maxLength={80} required disabled={!editar} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </label>
          <label>
            Código SUNAT
            <input
              value={form.codigo_oficial}
              maxLength={3}
              required
              disabled={!editar}
              placeholder="NIU"
              onChange={(e) => setForm({ ...form, codigo_oficial: e.target.value.toUpperCase() })}
            />
            <small>Catálogo N.° 03 de SUNAT (UN/ECE Rec. 20). Ej.: NIU unidad, KGM kilogramo, ZZ servicio.</small>
          </label>
          <label>
            Tipo
            <select value={form.tipo} disabled={!editar} onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
              {Object.entries(NOMBRE_TIPO_UNIDAD).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <small>Solo se convierten unidades del mismo tipo.</small>
          </label>
          {!nueva && (
            <label className="opcion">
              <input type="checkbox" checked={form.activo} disabled={!editar} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
              <span>
                Unidad activa
                <small>Una unidad inactiva no se puede usar en artículos nuevos.</small>
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
                {nueva ? "Crear unidad" : "Guardar cambios"}
              </BotonAccion>
            </div>
          )}
        </form>
      </Panel>
    </>
  );
}
