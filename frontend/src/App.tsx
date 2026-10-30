import { useEffect, useState, type ReactNode } from "react";
import Auditoria from "./paginas/Auditoria";
import Empresas from "./paginas/Empresas";
import Monedas from "./paginas/Monedas";
import Unidades from "./paginas/Unidades";
import Ingreso from "./paginas/Ingreso";
import Modulos from "./paginas/Modulos";
import Personalizacion from "./paginas/Personalizacion";
import Roles from "./paginas/Roles";
import Usuarios from "./paginas/Usuarios";
import { AvisosProvider } from "./avisos";
import { SesionProvider, useSesion } from "./sesion";

type Ruta = { ruta: string; nombre: string; permiso: string; pagina: () => ReactNode };

/**
 * Cada módulo agrega aquí sus pantallas. El menú muestra solo las que el usuario puede ver.
 * - grupo "negocio": módulos de operación (Solicitudes, Compras…); van arriba, siempre visibles.
 * - grupo "administracion": configuración del ERP; van plegadas en "Administración" al pie del menú.
 */
const MENU: { modulo: string; grupo: "negocio" | "administracion"; rutas: Ruta[] }[] = [
  {
    modulo: "maestros",
    grupo: "negocio",
    rutas: [
      { ruta: "empresas", nombre: "Empresas", permiso: "maestros.empresa.ver", pagina: () => <Empresas /> },
      { ruta: "monedas", nombre: "Monedas y tipo de cambio", permiso: "maestros.moneda.ver", pagina: () => <Monedas /> },
      { ruta: "unidades", nombre: "Unidades de medida", permiso: "maestros.unidad.ver", pagina: () => <Unidades /> },
    ],
  },
  {
    modulo: "seguridad",
    grupo: "administracion",
    rutas: [
      { ruta: "usuarios", nombre: "Usuarios", permiso: "seguridad.usuario.ver", pagina: () => <Usuarios /> },
      { ruta: "roles", nombre: "Roles", permiso: "seguridad.rol.ver", pagina: () => <Roles /> },
      { ruta: "modulos", nombre: "Módulos", permiso: "seguridad.modulo.ver", pagina: () => <Modulos /> },
      {
        ruta: "personalizacion",
        nombre: "Personalización",
        permiso: "seguridad.personalizacion.editar",
        pagina: () => <Personalizacion />,
      },
      { ruta: "auditoria", nombre: "Auditoría", permiso: "seguridad.auditoria.ver", pagina: () => <Auditoria /> },
    ],
  },
];

const rutaActual = () => window.location.hash.replace(/^#\/?/, "");

const CLAVE_ADMIN = "victoria.menu.administracion";
const leerAdminAbierto = () => {
  try {
    return localStorage.getItem(CLAVE_ADMIN) === "1";
  } catch {
    return false;
  }
};
const guardarAdminAbierto = (abierto: boolean) => {
  try {
    localStorage.setItem(CLAVE_ADMIN, abierto ? "1" : "0");
  } catch {
    /* sin almacenamiento: el grupo vuelve a plegarse al recargar */
  }
};

function Aplicacion() {
  const { sesion, cargando, salir, puede, marca } = useSesion();
  const [ruta, setRuta] = useState(rutaActual);
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [adminAbierto, setAdminAbierto] = useState(leerAdminAbierto);

  useEffect(() => {
    const cambio = () => {
      setRuta(rutaActual());
      setMenuAbierto(false);
    };
    window.addEventListener("hashchange", cambio);
    return () => window.removeEventListener("hashchange", cambio);
  }, []);

  // Al entrar a una pantalla de administración el grupo se abre para mostrar dónde estás.
  const rutaEsAdmin = MENU.some((m) => m.grupo === "administracion" && m.rutas.some((r) => r.ruta === ruta));
  useEffect(() => {
    if (rutaEsAdmin) setAdminAbierto(true);
  }, [ruta, rutaEsAdmin]);

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
  const negocio = secciones.filter((s) => s.grupo === "negocio");
  const administracion = secciones.filter((s) => s.grupo === "administracion").flatMap((s) => s.rutas);
  // La pantalla de inicio es la primera de negocio; si aún no hay, la primera de administración.
  const disponibles = [...negocio.flatMap((s) => s.rutas), ...administracion];
  const actual = disponibles.find((r) => r.ruta === ruta) ?? disponibles[0];
  const enAdministracion = administracion.some((r) => r.ruta === actual?.ruta);
  const verAdministracion = adminAbierto;
  const alternarAdmin = () => {
    const nuevo = !adminAbierto;
    setAdminAbierto(nuevo);
    guardarAdminAbierto(nuevo);
  };
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
        {marca.logo_url ? (
          <img className="marca-logo-movil" src={marca.logo_url} alt={marca.nombre_empresa ?? "Logo de la empresa"} />
        ) : (
          <span className="marca">Victoria ERP</span>
        )}
      </header>
      <nav className={menuAbierto ? "riel abierto" : "riel"} aria-label="Menú principal">
        <div className="riel-marca">
          {marca.logo_url && (
            <span className="riel-logo">
              <img src={marca.logo_url} alt={marca.nombre_empresa ?? "Logo de la empresa"} />
            </span>
          )}
          {marca.nombre_empresa && <p className="riel-empresa">{marca.nombre_empresa}</p>}
          <p className="marca">
            Victoria <span>ERP</span>
          </p>
        </div>
        <div className="riel-negocio">
        {negocio.map((s) => (
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
        {negocio.length === 0 && otrosActivos.length === 0 && (
          <p className="riel-ayuda">
            Aún no hay módulos de negocio activos.
            {puede("seguridad.modulo.ver") && (
              <>
                {" "}
                <a href="#/modulos">Activar módulos</a>
              </>
            )}
          </p>
        )}
        </div>
        {administracion.length > 0 && (
          <div className="riel-admin">
            <button
              type="button"
              className={enAdministracion && !verAdministracion ? "riel-admin-boton activo" : "riel-admin-boton"}
              aria-expanded={verAdministracion}
              aria-controls="menu-administracion"
              onClick={alternarAdmin}
            >
              <span aria-hidden="true">⚙</span> Administración
              <span className="riel-admin-flecha" aria-hidden="true">
                ▸
              </span>
            </button>
            {verAdministracion && (
              <div id="menu-administracion" className="riel-grupo riel-admin-lista">
                {administracion.map((r) => (
                  <a key={r.ruta} href={`#/${r.ruta}`} aria-current={actual?.ruta === r.ruta ? "page" : undefined}>
                    {r.nombre}
                  </a>
                ))}
              </div>
            )}
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
      <AvisosProvider>
        <Aplicacion />
      </AvisosProvider>
    </SesionProvider>
  );
}
