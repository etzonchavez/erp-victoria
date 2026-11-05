import { ArrowRight, Inbox } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { MODULOS, moduloPrincipal, type Pantalla } from "../navegacion";
import { useSesion } from "../sesion";

type Pendiente = { nombre: string; ruta: string; cantidad: number };

/** Inicio: pendientes por aprobar y las tareas del usuario agrupadas por módulo. */
export default function Inicio({ tareas, hayConfiguracion }: { tareas: Pantalla[]; hayConfiguracion: boolean }) {
  const { sesion, puede } = useSesion();
  const [pendientes, setPendientes] = useState<Pendiente[]>([]);
  const activos = new Set(sesion?.modulos.map((m) => m.codigo));

  useEffect(() => {
    const fuentes: { modulo: string; ruta: string; api: string; nombre: (n: number) => string }[] = [
      { modulo: "solicitudes", ruta: "solicitudes", api: "/solicitudes/bandeja", nombre: (n: number) => (n === 1 ? "solicitud por aprobar" : "solicitudes por aprobar") },
      { modulo: "compras", ruta: "ordenes-compra", api: "/compras/bandeja", nombre: (n: number) => (n === 1 ? "orden de compra por aprobar" : "órdenes de compra por aprobar") },
    ].filter((f) => activos.has(f.modulo));
    Promise.all(
      fuentes.map((f) =>
        api<unknown[]>(f.api)
          .then((xs) => ({ nombre: f.nombre(xs.length), ruta: f.ruta, cantidad: xs.length }))
          .catch(() => ({ nombre: "", ruta: f.ruta, cantidad: 0 })),
      ),
    ).then((r) => setPendientes(r.filter((p) => p.cantidad > 0)));
  }, [sesion?.modulos]);

  const grupos = MODULOS.map((m) => ({
    ...m,
    nombre: sesion?.modulos.find((x) => x.codigo === m.codigo)?.nombre ?? m.codigo,
    tareas: tareas.filter((t) => moduloPrincipal(t) === m.codigo),
  })).filter((g) => g.tareas.length > 0);
  const primerNombre = sesion?.usuario.nombre.split(" ")[0] ?? "";

  return (
    <>
      <div className="encabezado">
        <div>
          <h1>Hola, {primerNombre}</h1>
          <p>Elige qué quieres hacer. Solo ves las tareas a las que tienes acceso.</p>
        </div>
      </div>

      <section className="pendientes" aria-label="Pendientes">
        <Inbox aria-hidden="true" />
        {pendientes.length === 0 ? (
          <p>No tienes aprobaciones pendientes.</p>
        ) : (
          <ul>
            {pendientes.map((p) => (
              <li key={p.ruta}>
                <a href={`#/${p.ruta}?vista=por_aprobar`}>
                  <strong>{p.cantidad}</strong> {p.nombre}
                  <ArrowRight aria-hidden="true" size={16} />
                </a>
              </li>
            ))}
          </ul>
        )}
      </section>

      {grupos.length === 0 ? (
        <div className="vacio">
          <p>
            {hayConfiguracion
              ? "Aún no hay tareas disponibles para ti. Revisa la configuración o los módulos activos."
              : "Tu usuario aún no tiene tareas asignadas. Pide a un administrador que te asigne un rol."}
          </p>
          {puede("seguridad.modulo.ver") && <a href="#/modulos">Activar módulos</a>}
        </div>
      ) : (
        <div className="tarjetas-modulo">
          {grupos.map((g) => (
            <section key={g.codigo} className="tarjeta-modulo">
              <header>
                <span className="icono-modulo" aria-hidden="true">
                  <g.icono size={20} />
                </span>
                <h2>{g.nombre}</h2>
              </header>
              <ul>
                {g.tareas.map((t) => (
                  <li key={t.ruta}>
                    <a href={`#/${t.ruta}`} className="tarea">
                      <t.icono aria-hidden="true" size={18} />
                      <span>
                        <strong>{t.nombre}</strong>
                        <small>{t.descripcion}</small>
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
