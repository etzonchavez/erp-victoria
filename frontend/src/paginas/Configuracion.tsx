import { Encabezado } from "../componentes";
import { AREAS, type Pantalla } from "../navegacion";

/** Configuración: una sola entrada que agrupa por área lo que el usuario puede configurar. */
export default function Configuracion({ pantallas }: { pantallas: Pantalla[] }) {
  const areas = AREAS.map((a) => ({ ...a, pantallas: pantallas.filter((p) => p.area === a.codigo) })).filter(
    (a) => a.pantallas.length > 0,
  );
  return (
    <>
      <Encabezado
        titulo="Configuración"
        descripcion="Datos y reglas que el ERP usa en las tareas del día a día. Solo ves lo que tus roles permiten."
      />
      {areas.length === 0 ? (
        <div className="vacio">
          <p>No tienes opciones de configuración asignadas.</p>
        </div>
      ) : (
        <div className="tarjetas-modulo">
          {areas.map((a) => (
            <section key={a.codigo} className="tarjeta-modulo">
              <header>
                <span className="icono-modulo" aria-hidden="true">
                  <a.icono size={20} />
                </span>
                <h2>{a.nombre}</h2>
              </header>
              <ul>
                {a.pantallas.map((p) => (
                  <li key={p.ruta}>
                    <a href={`#/${p.ruta}`} className="tarea">
                      <p.icono aria-hidden="true" size={18} />
                      <span>
                        <strong>{p.nombre}</strong>
                        <small>{p.descripcion}</small>
                      </span>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
