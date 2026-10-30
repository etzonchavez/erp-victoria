import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, decimal, hoyLocal, type Moneda, type TipoCambio } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, Interruptor, MensajeError, Panel, fechaDia, useConfirmacion } from "../componentes";
import { useSesion } from "../sesion";

const BASE = "PEN";

export default function Monedas() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const [monedas, setMonedas] = useState<Moneda[]>([]);
  const [tipos, setTipos] = useState<TipoCambio[]>([]);
  const [filtro, setFiltro] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [errorTc, setErrorTc] = useState<unknown>(null);
  const [tc, setTc] = useState({ moneda: "USD", fecha: hoyLocal(), compra: "", venta: "" });
  const [registrando, setRegistrando] = useState(false);
  const registrado = useConfirmacion();
  const [cambiando, setCambiando] = useState<string | null>(null);
  const [nueva, setNueva] = useState(false);
  const [formMoneda, setFormMoneda] = useState({ codigo: "", nombre: "", simbolo: "", decimales: 2 });
  const [errorMoneda, setErrorMoneda] = useState<unknown>(null);
  const [creando, setCreando] = useState(false);

  const cargarMonedas = useCallback(async () => {
    try {
      setMonedas(await api<Moneda[]>("/maestros/monedas"));
    } catch (e) {
      setError(e);
    }
  }, []);
  const cargarTipos = useCallback(async () => {
    try {
      setTipos(await api<TipoCambio[]>(`/maestros/tipos-cambio?limite=60${filtro ? `&moneda=${filtro}` : ""}`));
    } catch (e) {
      setError(e);
    }
  }, [filtro]);

  useEffect(() => {
    cargarMonedas();
  }, [cargarMonedas]);
  useEffect(() => {
    cargarTipos();
  }, [cargarTipos]);

  const extranjeras = monedas.filter((m) => m.activo && m.codigo !== BASE);
  const yaRegistrado = tipos.find((t) => t.moneda === tc.moneda && t.fecha === tc.fecha);

  const registrar = async (e: FormEvent) => {
    e.preventDefault();
    setErrorTc(null);
    setRegistrando(true);
    try {
      await api<TipoCambio>("/maestros/tipos-cambio", { metodo: "PUT", cuerpo: { ...tc, moneda_base: BASE } });
      avisar(`Tipo de cambio ${tc.moneda} del ${fechaDia(tc.fecha)} ${yaRegistrado ? "corregido" : "registrado"}.`);
      registrado.confirmar();
      setTc({ ...tc, compra: "", venta: "" });
      await cargarTipos();
    } catch (err) {
      setErrorTc(err);
    } finally {
      setRegistrando(false);
    }
  };

  const cambiar = async (m: Moneda, activo: boolean) => {
    setError(null);
    setCambiando(m.codigo);
    try {
      await api(`/maestros/monedas/${m.codigo}`, { metodo: "PATCH", cuerpo: { activo } });
      avisar(`Moneda ${m.codigo} ${activo ? "activada" : "desactivada"}.`);
      await cargarMonedas();
    } catch (err) {
      setError(err);
    } finally {
      setCambiando(null);
    }
  };

  const crear = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMoneda(null);
    setCreando(true);
    try {
      await api<Moneda>("/maestros/monedas", { metodo: "POST", cuerpo: formMoneda });
      avisar(`Moneda ${formMoneda.codigo.toUpperCase()} agregada.`);
      setNueva(false);
      await cargarMonedas();
    } catch (err) {
      setErrorMoneda(err);
    } finally {
      setCreando(false);
    }
  };
  const cerrar = useCallback(() => setNueva(false), []);

  return (
    <>
      <Encabezado
        titulo="Monedas y tipo de cambio"
        descripcion="Registra el tipo de cambio de cada día hábil. Si un día no tiene registro, el ERP usa el último anterior (fines de semana y feriados)."
      />
      <MensajeError error={error} />

      {puede("maestros.tipo_cambio.registrar") && (
        <section className="bloque bloque-separado">
          <h2>Registrar tipo de cambio</h2>
          <form className="fila-formulario" onSubmit={registrar}>
            <label>
              Moneda
              <select value={tc.moneda} onChange={(e) => setTc({ ...tc, moneda: e.target.value })}>
                {extranjeras.map((m) => (
                  <option key={m.codigo} value={m.codigo}>
                    {m.codigo} — {m.nombre}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Fecha
              <input type="date" value={tc.fecha} max={hoyLocal()} required onChange={(e) => setTc({ ...tc, fecha: e.target.value })} />
            </label>
            <label>
              Compra ({BASE})
              <input
                type="number"
                inputMode="decimal"
                step="0.000001"
                min="0.000001"
                required
                placeholder="3.700"
                value={tc.compra}
                onChange={(e) => {
                  setTc({ ...tc, compra: e.target.value });
                  registrado.reiniciar();
                }}
              />
            </label>
            <label>
              Venta ({BASE})
              <input
                type="number"
                inputMode="decimal"
                step="0.000001"
                min="0.000001"
                required
                placeholder="3.720"
                value={tc.venta}
                onChange={(e) => {
                  setTc({ ...tc, venta: e.target.value });
                  registrado.reiniciar();
                }}
              />
            </label>
            <BotonAccion ocupado={registrando} listo={registrado.listo} textoListo="Registrado">
              {yaRegistrado ? "Corregir" : "Registrar"}
            </BotonAccion>
          </form>
          {yaRegistrado && (
            <p className="tenue">
              Ya hay un tipo de cambio {tc.moneda} para esa fecha (compra {decimal(yaRegistrado.compra)}, venta{" "}
              {decimal(yaRegistrado.venta)}). Si registras otro, lo reemplaza y queda en la auditoría.
            </p>
          )}
          <MensajeError error={errorTc} />
        </section>
      )}

      <div className="encabezado-seccion">
        <h2>Historial</h2>
        <label className="filtro">
          Moneda
          <select value={filtro} onChange={(e) => setFiltro(e.target.value)}>
            <option value="">Todas</option>
            {extranjeras.map((m) => (
              <option key={m.codigo} value={m.codigo}>
                {m.codigo}
              </option>
            ))}
          </select>
        </label>
      </div>
      {tipos.length === 0 ? (
        <div className="vacio">
          <p>Aún no hay tipos de cambio registrados.</p>
        </div>
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Moneda</th>
                <th className="numero">Compra</th>
                <th className="numero">Venta</th>
                <th>Origen</th>
              </tr>
            </thead>
            <tbody>
              {tipos.map((t) => (
                <tr key={t.id}>
                  <td className="numero">{fechaDia(t.fecha)}</td>
                  <td>
                    {t.moneda} → {t.moneda_base}
                  </td>
                  <td className="numero">{decimal(t.compra)}</td>
                  <td className="numero">{decimal(t.venta)}</td>
                  <td className="tenue">{t.fuente === "manual" ? "Manual" : t.fuente}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="encabezado-seccion">
        <h2>Monedas</h2>
        {puede("maestros.moneda.editar") && (
          <button
            className="boton"
            onClick={() => {
              setFormMoneda({ codigo: "", nombre: "", simbolo: "", decimales: 2 });
              setErrorMoneda(null);
              setNueva(true);
            }}
          >
            Agregar moneda
          </button>
        )}
      </div>
      <ul className="lista-modulos">
        {monedas.map((m) => (
          <li key={m.codigo}>
            <div>
              <p className="fuerte">
                {m.codigo} · {m.nombre}
              </p>
              <p className="tenue">
                Símbolo {m.simbolo} · {m.decimales} decimales
              </p>
            </div>
            <Estado activo={m.activo} si="Activa" no="Inactiva" />
            <Interruptor
              etiqueta={`${m.activo ? "Desactivar" : "Activar"} ${m.nombre}`}
              activo={m.activo}
              deshabilitado={!puede("maestros.moneda.editar")}
              ocupado={cambiando === m.codigo}
              onCambio={(v) => cambiar(m, v)}
            />
          </li>
        ))}
      </ul>

      <Panel titulo="Agregar moneda" abierto={nueva} onCerrar={cerrar}>
        <form className="formulario" onSubmit={crear}>
          <label>
            Código ISO 4217
            <input
              value={formMoneda.codigo}
              maxLength={3}
              required
              placeholder="BRL"
              onChange={(e) => setFormMoneda({ ...formMoneda, codigo: e.target.value.toUpperCase() })}
            />
          </label>
          <label>
            Nombre
            <input value={formMoneda.nombre} maxLength={60} required onChange={(e) => setFormMoneda({ ...formMoneda, nombre: e.target.value })} />
          </label>
          <label>
            Símbolo
            <input value={formMoneda.simbolo} maxLength={5} required onChange={(e) => setFormMoneda({ ...formMoneda, simbolo: e.target.value })} />
          </label>
          <label>
            Decimales
            <input
              type="number"
              min={0}
              max={4}
              value={formMoneda.decimales}
              onChange={(e) => setFormMoneda({ ...formMoneda, decimales: Number(e.target.value) })}
            />
          </label>
          <MensajeError error={errorMoneda} />
          <div className="acciones">
            <button type="button" className="boton" onClick={cerrar}>
              Cancelar
            </button>
            <BotonAccion ocupado={creando} textoOcupado="Agregando…">
              Agregar moneda
            </BotonAccion>
          </div>
        </form>
      </Panel>
    </>
  );
}
