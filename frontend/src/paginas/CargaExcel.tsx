import { useEffect, useRef, useState } from "react";
import { api, descargar } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, MensajeError } from "../componentes";
import { SelectorEmpresa, useEmpresaActiva } from "../empresa";
import { useSesion } from "../sesion";

type TipoCarga = { codigo: string; nombre: string; permiso: string; por_empresa: boolean };
type Resultado = {
  tipo: string;
  total: number;
  validas: number;
  errores: number;
  cargado: boolean;
  filas: { fila: number; clave: string; error: string | null }[];
};

export default function CargaExcel() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const { empresas, empresa, elegir } = useEmpresaActiva();
  const [tipos, setTipos] = useState<TipoCarga[]>([]);
  const [tipo, setTipo] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const entrada = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api<TipoCarga[]>("/importacion/tipos")
      .then((t) => {
        const permitidos = t.filter((x) => puede(x.permiso));
        setTipos(permitidos);
        setTipo((actual) => actual || permitidos[0]?.codigo || "");
      })
      .catch(setError);
  }, [puede]);

  const actual = tipos.find((t) => t.codigo === tipo);
  const reiniciar = () => {
    setResultado(null);
    setError(null);
  };

  const plantilla = async () => {
    setError(null);
    try {
      await descargar(`/importacion/${tipo}/plantilla`, `victoria-${tipo}.xlsx`);
    } catch (e) {
      setError(e);
    }
  };

  const enviar = async (accion: "validar" | "cargar") => {
    if (!archivo || !actual) return;
    setOcupado(accion);
    setError(null);
    try {
      const r = await api<Resultado>(`/importacion/${tipo}/${accion}`, {
        metodo: "POST",
        archivo: { campo: "archivo", valor: archivo },
        campos: actual.por_empresa && empresa ? { empresa_id: empresa.id } : {},
      });
      setResultado(r);
      if (r.cargado) {
        avisar(`${r.total} ${r.total === 1 ? "fila cargada" : "filas cargadas"} de ${actual.nombre.toLowerCase()}.`);
        setArchivo(null);
        if (entrada.current) entrada.current.value = "";
      }
    } catch (e) {
      setError(e);
    } finally {
      setOcupado(null);
    }
  };

  return (
    <>
      <Encabezado
        titulo="Carga desde Excel"
        descripcion="Carga muchos registros a la vez. Primero se valida todo el archivo con las mismas reglas de las pantallas; si una fila tiene un error no se carga nada."
      />
      <MensajeError error={error} />
      {tipos.length === 0 ? (
        <div className="vacio">
          <p>No tienes permiso para cargar ningún maestro.</p>
        </div>
      ) : (
        <div className="pasos-carga">
          <section className="bloque">
            <h2>1. Qué vas a cargar</h2>
            <div className="pestanas">
              {tipos.map((t) => (
                <button
                  key={t.codigo}
                  role="tab"
                  aria-selected={t.codigo === tipo}
                  onClick={() => {
                    setTipo(t.codigo);
                    setArchivo(null);
                    if (entrada.current) entrada.current.value = "";
                    reiniciar();
                  }}
                >
                  {t.nombre}
                </button>
              ))}
            </div>
            {actual?.por_empresa && (
              <div>
                <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={(id) => (elegir(id), reiniciar())} />
              </div>
            )}
            <div>
              <button className="boton" onClick={plantilla}>
                Descargar plantilla de {actual?.nombre.toLowerCase()}
              </button>
              <p className="tenue">La hoja Instrucciones explica cada columna y trae un ejemplo.</p>
            </div>
          </section>

          <section className="bloque">
            <h2>2. Tu archivo</h2>
            <input
              ref={entrada}
              type="file"
              accept=".xlsx"
              onChange={(e) => {
                setArchivo(e.target.files?.[0] ?? null);
                reiniciar();
              }}
            />
            <div className="acciones-linea">
              <BotonAccion primario={false} ocupado={ocupado === "validar"} textoOcupado="Validando…" disabled={!archivo || ocupado !== null} onClick={() => enviar("validar")}>
                Validar archivo
              </BotonAccion>
              <BotonAccion
                ocupado={ocupado === "cargar"}
                textoOcupado="Cargando…"
                disabled={!archivo || !resultado || resultado.errores > 0 || resultado.cargado || ocupado !== null}
                onClick={() => enviar("cargar")}
              >
                {resultado && !resultado.cargado && resultado.errores === 0 ? `Cargar ${resultado.total} filas` : "Cargar"}
              </BotonAccion>
            </div>
            <p className="tenue">Hasta 5000 filas y 5 MB. Valida primero; el botón Cargar se habilita cuando no hay errores.</p>
          </section>

          {resultado && (
            <section className="bloque resultado-carga">
              <h2>3. Resultado</h2>
              {resultado.cargado ? (
                <div className="aviso aviso-exito">Se cargaron las {resultado.total} filas.</div>
              ) : resultado.errores > 0 ? (
                <div className="aviso aviso-error">
                  {resultado.errores} de {resultado.total} filas tienen errores. Corrígelas en el archivo y vuelve a validar: no se
                  cargó nada.
                </div>
              ) : (
                <div className="aviso aviso-info">Las {resultado.total} filas son válidas. Ya puedes cargar.</div>
              )}
              <div className="tabla-contenedor">
                <table className="tabla tabla-compacta">
                  <thead>
                    <tr>
                      <th className="numero">Fila</th>
                      <th>Registro</th>
                      <th>Resultado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultado.filas.map((f) => (
                      <tr key={f.fila} className={f.error ? "fila-alerta" : undefined}>
                        <td className="numero">{f.fila}</td>
                        <td>{f.clave}</td>
                        <td>{f.error ?? <span className="estado estado-si">{resultado.cargado ? "Cargada" : "Correcta"}</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {resultado.total > resultado.filas.length && (
                <p className="tenue">Se muestran las primeras {resultado.filas.length} filas (primero las que tienen errores).</p>
              )}
            </section>
          )}
        </div>
      )}
    </>
  );
}
