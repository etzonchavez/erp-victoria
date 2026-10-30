import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, type Empresa, type Moneda, type Pais, type UnidadNegocio } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, Interruptor, MensajeError, Panel } from "../componentes";
import { useSesion } from "../sesion";

type Formulario = {
  pais: string;
  identificacion_fiscal: string;
  razon_social: string;
  nombre_comercial: string;
  direccion_fiscal: string;
  moneda_funcional: string;
};
const VACIO: Formulario = {
  pais: "pe",
  identificacion_fiscal: "",
  razon_social: "",
  nombre_comercial: "",
  direccion_fiscal: "",
  moneda_funcional: "PEN",
};

export default function Empresas() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [paises, setPaises] = useState<Pais[]>([]);
  const [monedas, setMonedas] = useState<Moneda[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<Empresa | "nueva" | null>(null);
  const [form, setForm] = useState<Formulario>(VACIO);
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);
  const [nuevaUn, setNuevaUn] = useState({ codigo: "", nombre: "" });
  const [creandoUn, setCreandoUn] = useState(false);
  const [cambiandoUn, setCambiandoUn] = useState<string | null>(null);
  const editar = puede("maestros.empresa.editar");

  const cargar = useCallback(async () => {
    try {
      const lista = await api<Empresa[]>("/maestros/empresas");
      setEmpresas(lista);
      setEditando((actual) => (actual && actual !== "nueva" ? (lista.find((e) => e.id === actual.id) ?? null) : actual));
    } catch (e) {
      setError(e);
    }
  }, []);

  useEffect(() => {
    cargar();
    api<Pais[]>("/maestros/paises").then(setPaises).catch(setError);
    if (puede("maestros.moneda.ver")) api<Moneda[]>("/maestros/monedas").then(setMonedas).catch(setError);
  }, [cargar, puede]);

  const abrir = (e: Empresa | "nueva") => {
    setErrorForm(null);
    setNuevaUn({ codigo: "", nombre: "" });
    setEditando(e);
    setForm(
      e === "nueva"
        ? VACIO
        : {
            pais: e.pais,
            identificacion_fiscal: e.identificacion_fiscal,
            razon_social: e.razon_social,
            nombre_comercial: e.nombre_comercial ?? "",
            direccion_fiscal: e.direccion_fiscal ?? "",
            moneda_funcional: e.moneda_funcional,
          },
    );
  };
  const cerrar = useCallback(() => setEditando(null), []);
  const nueva = editando === "nueva";
  const pais = paises.find((p) => p.codigo === form.pais);
  const nombreId = pais?.nombre_identificacion_fiscal ?? "Identificación fiscal";

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setGuardando(true);
    setErrorForm(null);
    try {
      if (nueva) {
        const creada = await api<Empresa>("/maestros/empresas", { metodo: "POST", cuerpo: form });
        avisar(`Empresa ${creada.razon_social} creada con la unidad de negocio Principal.`);
        await cargar();
        setEditando(creada);
      } else if (editando) {
        await api(`/maestros/empresas/${editando.id}`, {
          metodo: "PATCH",
          cuerpo: {
            razon_social: form.razon_social,
            nombre_comercial: form.nombre_comercial,
            direccion_fiscal: form.direccion_fiscal,
          },
        });
        avisar(`Cambios de ${form.razon_social} guardados.`);
        setEditando(null);
        await cargar();
      }
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const cambiarEstado = async (empresa: Empresa, activo: boolean) => {
    setErrorForm(null);
    try {
      await api(`/maestros/empresas/${empresa.id}`, { metodo: "PATCH", cuerpo: { activo } });
      avisar(`Empresa ${activo ? "activada" : "desactivada"}.`);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    }
  };

  const crearUn = async (e: FormEvent) => {
    e.preventDefault();
    if (!editando || editando === "nueva") return;
    setCreandoUn(true);
    setErrorForm(null);
    try {
      const un = await api<UnidadNegocio>(`/maestros/empresas/${editando.id}/unidades-negocio`, {
        metodo: "POST",
        cuerpo: nuevaUn,
      });
      avisar(`Unidad de negocio ${un.codigo} creada.`);
      setNuevaUn({ codigo: "", nombre: "" });
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setCreandoUn(false);
    }
  };

  const cambiarUn = async (un: UnidadNegocio, activo: boolean) => {
    setCambiandoUn(un.id);
    setErrorForm(null);
    try {
      await api(`/maestros/unidades-negocio/${un.id}`, { metodo: "PATCH", cuerpo: { activo } });
      avisar(`Unidad ${un.codigo} ${activo ? "activada" : "desactivada"}.`);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setCambiandoUn(null);
    }
  };

  const monedasActivas = monedas.filter((m) => m.activo || m.codigo === form.moneda_funcional);

  return (
    <>
      <Encabezado
        titulo="Empresas"
        descripcion="Empresas legales que operan en el ERP y sus unidades de negocio. Una instalación puede tener varias empresas."
        accion={
          editar && (
            <button className="boton boton-primario" onClick={() => abrir("nueva")}>
              Crear empresa
            </button>
          )
        }
      />
      <MensajeError error={error} />
      {empresas.length === 0 ? (
        <div className="vacio">
          <p>Aún no hay empresas. Crea la primera para empezar a configurar el ERP.</p>
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Razón social</th>
                <th>RUC / Id. fiscal</th>
                <th>Moneda funcional</th>
                <th>Unidades de negocio</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {empresas.map((e) => (
                <tr key={e.id} onClick={() => abrir(e)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrir(e)}>
                  <td>
                    <span className="fuerte">{e.razon_social}</span>
                    {e.nombre_comercial && <p className="tenue">{e.nombre_comercial}</p>}
                  </td>
                  <td className="numero">{e.identificacion_fiscal}</td>
                  <td>{e.moneda_funcional}</td>
                  <td>
                    {e.unidades
                      .filter((u) => u.activo)
                      .map((u) => (
                        <span key={u.id} className="etiqueta">
                          {u.nombre}
                        </span>
                      ))}
                  </td>
                  <td>
                    <Estado activo={e.activo} si="Activa" no="Inactiva" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel titulo={nueva ? "Crear empresa" : "Empresa"} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          {nueva && (
            <label>
              País
              <select
                value={form.pais}
                onChange={(e) => {
                  const p = paises.find((x) => x.codigo === e.target.value);
                  setForm({ ...form, pais: e.target.value, moneda_funcional: p?.moneda ?? form.moneda_funcional });
                }}
              >
                {paises.map((p) => (
                  <option key={p.codigo} value={p.codigo}>
                    {p.nombre}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            {nombreId}
            <input
              value={form.identificacion_fiscal}
              inputMode="numeric"
              maxLength={20}
              disabled={!nueva}
              required
              placeholder={form.pais === "pe" ? "11 dígitos" : undefined}
              onChange={(e) => setForm({ ...form, identificacion_fiscal: e.target.value })}
            />
            {!nueva && <small>No se puede cambiar: identifica a la empresa ante el fisco.</small>}
          </label>
          <label>
            Razón social
            <input
              value={form.razon_social}
              maxLength={200}
              required
              disabled={!editar}
              onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
            />
          </label>
          <label>
            <span>
              Nombre comercial <span className="tenue">(opcional)</span>
            </span>
            <input
              value={form.nombre_comercial}
              maxLength={150}
              disabled={!editar}
              onChange={(e) => setForm({ ...form, nombre_comercial: e.target.value })}
            />
          </label>
          <label>
            <span>
              Dirección fiscal <span className="tenue">(opcional)</span>
            </span>
            <input
              value={form.direccion_fiscal}
              maxLength={300}
              disabled={!editar}
              onChange={(e) => setForm({ ...form, direccion_fiscal: e.target.value })}
            />
          </label>
          <label>
            Moneda funcional
            <select
              value={form.moneda_funcional}
              disabled={!nueva}
              onChange={(e) => setForm({ ...form, moneda_funcional: e.target.value })}
            >
              {(monedasActivas.length ? monedasActivas : [{ codigo: form.moneda_funcional, nombre: "" }]).map((m) => (
                <option key={m.codigo} value={m.codigo}>
                  {m.codigo} {m.nombre && `— ${m.nombre}`}
                </option>
              ))}
            </select>
            <small>
              {nueva
                ? "Moneda en la que la empresa lleva su contabilidad. No se podrá cambiar después."
                : "No se puede cambiar: la contabilidad se lleva en esta moneda."}
            </small>
          </label>

          <MensajeError error={errorForm} />
          {editar && (
            <div className="acciones">
              {!nueva && editando && (
                <button
                  type="button"
                  className="boton"
                  style={{ marginRight: "auto" }}
                  onClick={() => cambiarEstado(editando, !editando.activo)}
                >
                  {editando.activo ? "Desactivar empresa" : "Activar empresa"}
                </button>
              )}
              <button type="button" className="boton" onClick={cerrar}>
                Cancelar
              </button>
              <BotonAccion ocupado={guardando} textoOcupado={nueva ? "Creando…" : "Guardando…"}>
                {nueva ? "Crear empresa" : "Guardar cambios"}
              </BotonAccion>
            </div>
          )}
        </form>

        {!nueva && editando && (
          <section className="subseccion">
            <h3>Unidades de negocio</h3>
            <p className="tenue">Sedes, divisiones o líneas de negocio. Los centros de costo y las compras se asignan a una de ellas.</p>
            <ul className="lista-simple">
              {editando.unidades.map((u) => (
                <li key={u.id}>
                  <div>
                    <p className="fuerte">{u.nombre}</p>
                    <code>{u.codigo}</code>
                  </div>
                  <Interruptor
                    etiqueta={`${u.activo ? "Desactivar" : "Activar"} ${u.nombre}`}
                    activo={u.activo}
                    deshabilitado={!editar}
                    ocupado={cambiandoUn === u.id}
                    onCambio={(v) => cambiarUn(u, v)}
                  />
                </li>
              ))}
            </ul>
            {editar && (
              <form className="fila-formulario" onSubmit={crearUn}>
                <label>
                  Código
                  <input
                    value={nuevaUn.codigo}
                    maxLength={20}
                    required
                    placeholder="LIMA"
                    onChange={(e) => setNuevaUn({ ...nuevaUn, codigo: e.target.value.toUpperCase() })}
                  />
                </label>
                <label>
                  Nombre
                  <input
                    value={nuevaUn.nombre}
                    maxLength={150}
                    required
                    placeholder="Sede Lima"
                    onChange={(e) => setNuevaUn({ ...nuevaUn, nombre: e.target.value })}
                  />
                </label>
                <BotonAccion primario={false} ocupado={creandoUn} textoOcupado="Agregando…">
                  Agregar
                </BotonAccion>
              </form>
            )}
          </section>
        )}
      </Panel>
    </>
  );
}
