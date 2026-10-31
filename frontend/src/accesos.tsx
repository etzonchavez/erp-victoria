import { useEffect, useState } from "react";
import { api, type Usuario } from "./api";
import { useAvisos } from "./avisos";
import { BotonAccion, MensajeError } from "./componentes";
import { type EmpresaResumen } from "./empresa";

type Acceso = { empresa_id: string; todas_unidades: boolean; unidades: string[] };

/** Empresas y unidades de negocio a las que accede un usuario (se muestra en su ficha). */
export function AccesosUsuario({ usuario, editar, onCambio }: { usuario: Usuario; editar: boolean; onCambio: () => void }) {
  const { avisar } = useAvisos();
  const [empresas, setEmpresas] = useState<EmpresaResumen[]>([]);
  const [accesos, setAccesos] = useState<Map<string, Acceso>>(new Map());
  const [original, setOriginal] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (usuario.es_administrador) return;
    Promise.all([
      api<EmpresaResumen[]>("/maestros/empresas/accesibles"),
      api<Acceso[]>(`/maestros/usuarios/${usuario.id}/accesos`),
    ])
      .then(([e, a]) => {
        setEmpresas(e);
        setAccesos(new Map(a.map((x) => [x.empresa_id, x])));
        setOriginal(JSON.stringify(a));
      })
      .catch(setError);
  }, [usuario]);

  if (usuario.es_administrador)
    return (
      <section className="subseccion">
        <h3>Empresas y unidades de negocio</h3>
        <p className="tenue">El administrador tiene acceso a todas las empresas y unidades de negocio.</p>
      </section>
    );

  const lista = [...accesos.values()];
  const sinCambios = JSON.stringify(lista) === original;
  const cambiar = (empresaId: string, cambio: Partial<Acceso> | null) => {
    const n = new Map(accesos);
    if (cambio === null) n.delete(empresaId);
    else n.set(empresaId, { empresa_id: empresaId, todas_unidades: true, unidades: [], ...accesos.get(empresaId), ...cambio });
    setAccesos(n);
  };

  const guardar = async () => {
    setGuardando(true);
    setError(null);
    try {
      const r = await api<Acceso[]>(`/maestros/usuarios/${usuario.id}/accesos`, { metodo: "PUT", cuerpo: { accesos: lista } });
      setAccesos(new Map(r.map((x) => [x.empresa_id, x])));
      setOriginal(JSON.stringify(r));
      avisar(`Accesos de ${usuario.nombre} guardados.`);
      onCambio();
    } catch (e) {
      setError(e);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <section className="subseccion">
      <h3>Empresas y unidades de negocio</h3>
      <p className="tenue">
        El usuario solo ve y opera en lo que marques aquí. Sin empresas asignadas no ve ninguna.
      </p>
      {empresas.length === 0 && <p className="tenue">No hay empresas activas que puedas asignar.</p>}
      <ul className="lista-simple">
        {empresas.map((e) => {
          const a = accesos.get(e.id);
          return (
            <li key={e.id} className="li-acceso">
              <div>
                <label className="opcion">
                  <input type="checkbox" checked={!!a} disabled={!editar} onChange={(ev) => cambiar(e.id, ev.target.checked ? {} : null)} />
                  <span className="fuerte">{e.razon_social}</span>
                </label>
                {a && (
                  <div className="unidades-acceso">
                    <label className="opcion">
                      <input
                        type="checkbox"
                        checked={a.todas_unidades}
                        disabled={!editar}
                        onChange={(ev) => cambiar(e.id, { todas_unidades: ev.target.checked, unidades: [] })}
                      />
                      <span>Todas las unidades de negocio (incluidas las futuras)</span>
                    </label>
                    {!a.todas_unidades &&
                      e.unidades.map((u) => (
                        <label key={u.id} className="opcion">
                          <input
                            type="checkbox"
                            checked={a.unidades.includes(u.id)}
                            disabled={!editar}
                            onChange={(ev) =>
                              cambiar(e.id, {
                                unidades: ev.target.checked ? [...a.unidades, u.id] : a.unidades.filter((x) => x !== u.id),
                              })
                            }
                          />
                          <span>{u.nombre}</span>
                        </label>
                      ))}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <MensajeError error={error} />
      {editar && empresas.length > 0 && (
        <div>
          <BotonAccion primario={false} ocupado={guardando} disabled={sinCambios} onClick={guardar}>
            Guardar accesos
          </BotonAccion>
        </div>
      )}
    </section>
  );
}
