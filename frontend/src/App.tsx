import { useEffect, useState, type ReactNode } from "react";
import Auditoria from "./paginas/Auditoria";
import Ingreso from "./paginas/Ingreso";
import Modulos from "./paginas/Modulos";
import Roles from "./paginas/Roles";
import Usuarios from "./paginas/Usuarios";
import { SesionProvider, useSesion } from "./sesion";

type Ruta = { ruta: string; nombre: string; permiso: string; pagina: () => ReactNode };

// Cada módulo agrega aquí sus pantallas. El menú muestra solo las que el usuario puede ver.
const MENU: { modulo: string; rutas: Ruta[] }[] = [
  {
    modulo: "seguridad",
    rutas: [
      { ruta: "usuarios", nombre: "Usuarios", permiso: "seguridad.usuario.ver", pagina: () => <Usuarios /> },
      { ruta: "roles", nombre: "Roles", permiso: "seguridad.rol.ver", pagina: () => <Roles /> },
      { ruta: "modulos", nombre: "Módulos", permiso: "seguridad.modulo.ver", pagina: () => <Modulos /> },
      { ruta: "auditoria", nombre: "Auditoría", permiso: "seguridad.auditoria.ver", pagina: () => <Auditoria /> },
    ],
  },
];

const rutaActual = () => window.location.hash.replace(/^#\/?/, "");

function Aplicacion() {
  const { sesion, cargando, salir, puede } = useSesion();
  const [ruta, setRuta] = useState(rutaActual);
  const [menuAbierto, setMenuAbierto] = useState(false);

  useEffect(() => {
    const cambio = () => {
      setRuta(rutaActual());
      setMenuAbierto(false);
    };
    window.addEventListener("hashchange", cambio);
    return () => window.removeEventListener("hashchange", cambio);
  }, []);

  if (cargando) return <div className="cargando">Cargando…</div>;
  if (!sesion) return <Ingreso />;

  const activos = new Set(sesion.modulos.map((m) => m.codigo));
  const secciones = MENU.filter((s) => activos.has(s.modulo))
    .map((s) => ({
      ...s,
      nombre: sesion.modulos.find((m) => m.codigo === s.modulo)?.nombre ?? s.modulo,
      rutas: s.rutas.filter((r) => puede(r.permiso)),
    }))
    .filter((s) => s.rutas.length > 0);
  const disponibles = secciones.flatMap((s) => s.rutas);
  const actual = disponibles.find((r) => r.ruta === ruta) ?? disponibles[0];
  const iniciales = sesion.usuario.nombre
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
  const otrosActivos = sesion.modulos.filter((m) => !MENU.some((s) => s.modulo === m.codigo));

  return (
    <div className="marco">
      <header className="barra-movil">
        <button className="boton-icono" onClick={() => setMenuAbierto(!menuAbierto)} aria-expanded={menuAbierto}>
          ☰
        </button>
        <span className="marca">Victoria</span>
      </header>
      <nav className={menuAbierto ? "riel abierto" : "riel"} aria-label="Menú principal">
        <p className="marca">Victoria</p>
        {secciones.map((s) => (
          <div key={s.modulo} className="riel-grupo">
            <p className="riel-modulo">{s.nombre}</p>
            {s.rutas.map((r) => (
              <a key={r.ruta} href={`#/${r.ruta}`} aria-current={actual?.ruta === r.ruta ? "page" : undefined}>
                {r.nombre}
              </a>
            ))}
          </div>
        ))}
        {otrosActivos.length > 0 && (
          <div className="riel-grupo">
            <p className="riel-modulo">Próximamente</p>
            {otrosActivos.map((m) => (
              <span key={m.codigo} className="riel-pendiente">
                {m.nombre}
              </span>
            ))}
          </div>
        )}
        <div className="riel-usuario">
          <span className="avatar" aria-hidden="true">
            {iniciales}
          </span>
          <div>
            <p>{sesion.usuario.nombre}</p>
            <button className="enlace" onClick={salir}>
              Cerrar sesión
            </button>
          </div>
        </div>
      </nav>
      <main className="contenido">
        {actual ? (
          actual.pagina()
        ) : (
          <div className="vacio">
            <p>Tu usuario aún no tiene roles asignados. Pide a un administrador que te asigne uno.</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <SesionProvider>
      <Aplicacion />
    </SesionProvider>
  );
}
