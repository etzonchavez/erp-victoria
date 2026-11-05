import { Bell, ChevronDown, LogOut, Menu, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { AvisosProvider } from "./avisos";
import { AREAS, ICONO_CONFIGURACION, ICONO_INICIO, MODULOS, moduloPrincipal, pantallasVisibles } from "./navegacion";
import Configuracion from "./paginas/Configuracion";
import Ingreso from "./paginas/Ingreso";
import Inicio from "./paginas/Inicio";
import { SesionProvider, useSesion } from "./sesion";

// Las pantallas se registran en navegacion.tsx; aquí solo está el marco (barra superior y menú).

const rutaActual = () => window.location.hash.replace(/^#\/?/, "").split("?")[0];

const CLAVE_GRUPOS = "victoria.menu.grupos";
const leerGrupos = (): Record<string, boolean> => {
  try {
    return JSON.parse(localStorage.getItem(CLAVE_GRUPOS) ?? "{}");
  } catch {
    return {};
  }
};
const guardarGrupos = (g: Record<string, boolean>) => {
  try {
    localStorage.setItem(CLAVE_GRUPOS, JSON.stringify(g));
  } catch {
    /* sin almacenamiento: los grupos vuelven a su estado inicial al recargar */
  }
};

function Aplicacion() {
  const { sesion, cargando, salir, puede, marca } = useSesion();
  const [ruta, setRuta] = useState(rutaActual);
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [usuarioAbierto, setUsuarioAbierto] = useState(false);
  const [grupos, setGrupos] = useState(leerGrupos);
  const botonMenu = useRef<HTMLButtonElement>(null);

  const cerrarMenu = useCallback(() => setMenuAbierto(false), []);
  useEffect(() => {
    const cambio = () => {
      setRuta(rutaActual());
      setMenuAbierto(false);
      setUsuarioAbierto(false);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", cambio);
    return () => window.removeEventListener("hashchange", cambio);
  }, []);
  useEffect(() => {
    if (!menuAbierto && !usuarioAbierto) return;
    const tecla = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (menuAbierto) botonMenu.current?.focus();
      setMenuAbierto(false);
      setUsuarioAbierto(false);
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [menuAbierto, usuarioAbierto]);

  if (cargando) return <div className="cargando">Cargando…</div>;
  if (!sesion) return <Ingreso />;

  const activos = new Set(sesion.modulos.map((m) => m.codigo));
  const visibles = pantallasVisibles(activos, puede);
  const tareas = visibles.filter((p) => p.tipo === "tarea");
  const configuracion = visibles.filter((p) => p.tipo === "configuracion");
  const actual = visibles.find((p) => p.ruta === ruta);
  const enConfiguracion = ruta === "configuracion" || actual?.tipo === "configuracion";
  const titulo = actual?.nombre ?? (ruta === "configuracion" ? "Configuración" : "Inicio");

  const modulosMenu = MODULOS.map((m) => ({
    ...m,
    nombre: sesion.modulos.find((x) => x.codigo === m.codigo)?.nombre ?? m.codigo,
    tareas: tareas.filter((t) => moduloPrincipal(t) === m.codigo),
  })).filter((m) => m.tareas.length > 0);
  // Un grupo está abierto si el usuario lo abrió, o si contiene la pantalla actual
  const abierto = (clave: string, contieneActual: boolean) => grupos[clave] ?? contieneActual;
  const alternar = (clave: string, contieneActual: boolean) => {
    const nuevo = { ...grupos, [clave]: !abierto(clave, contieneActual) };
    setGrupos(nuevo);
    guardarGrupos(nuevo);
  };
  const iniciales = sesion.usuario.nombre
    .split(" ")
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();

  let pagina;
  if (actual) pagina = actual.pagina();
  else if (ruta === "configuracion") pagina = <Configuracion pantallas={configuracion} />;
  else pagina = <Inicio tareas={tareas} hayConfiguracion={configuracion.length > 0} />;

  return (
    <div className="marco">
      <header className="barra-superior">
        <button
          ref={botonMenu}
          className="boton-icono"
          onClick={() => setMenuAbierto(!menuAbierto)}
          aria-expanded={menuAbierto}
          aria-controls="menu-principal"
          aria-label={menuAbierto ? "Cerrar menú" : "Abrir menú"}
        >
          {menuAbierto ? <X size={20} /> : <Menu size={20} />}
        </button>
        <a href="#/inicio" className="barra-marca" aria-label="Ir a Inicio">
          {marca.logo_url ? (
            <img src={marca.logo_url} alt={marca.nombre_empresa ?? "Logo de la empresa"} />
          ) : (
            <span className="marca">
              Victoria <span>ERP</span>
            </span>
          )}
        </a>
        <span className="barra-titulo">{titulo}</span>
        <div className="barra-derecha">
          <button className="boton-icono" disabled title="Notificaciones: llegan en el próximo release" aria-label="Notificaciones (próximamente)">
            <Bell size={20} />
          </button>
          <div className="menu-usuario">
            <button className="boton-usuario" onClick={() => setUsuarioAbierto(!usuarioAbierto)} aria-expanded={usuarioAbierto} aria-haspopup="menu">
              <span className="avatar" aria-hidden="true">
                {iniciales}
              </span>
              <span className="boton-usuario-nombre">{sesion.usuario.nombre}</span>
              <ChevronDown size={16} aria-hidden="true" />
            </button>
            {usuarioAbierto && (
              <div className="menu-usuario-lista" role="menu">
                <p>
                  <strong>{sesion.usuario.nombre}</strong>
                  <span>{sesion.usuario.email}</span>
                </p>
                <button role="menuitem" onClick={salir}>
                  <LogOut size={16} aria-hidden="true" /> Cerrar sesión
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {menuAbierto && <div className="velo" onClick={cerrarMenu} aria-hidden="true" />}
      <nav id="menu-principal" className={menuAbierto ? "riel abierto" : "riel"} aria-label="Menú principal" hidden={!menuAbierto}>
        {marca.nombre_empresa && <p className="riel-empresa">{marca.nombre_empresa}</p>}
        <a href="#/inicio" className="riel-enlace" aria-current={!actual && ruta !== "configuracion" ? "page" : undefined}>
          <ICONO_INICIO size={18} aria-hidden="true" /> Inicio
        </a>
        {modulosMenu.map((m) => {
          // Un módulo con una sola tarea va directo, sin grupo que desplegar
          if (m.tareas.length === 1) {
            const t = m.tareas[0];
            return (
              <a key={m.codigo} href={`#/${t.ruta}`} className="riel-enlace" aria-current={actual?.ruta === t.ruta ? "page" : undefined}>
                <m.icono size={18} aria-hidden="true" /> {t.nombre}
              </a>
            );
          }
          const contiene = m.tareas.some((t) => t.ruta === actual?.ruta);
          const verGrupo = abierto(m.codigo, contiene);
          return (
            <div key={m.codigo} className="riel-grupo">
              <button className="riel-modulo" aria-expanded={verGrupo} onClick={() => alternar(m.codigo, contiene)}>
                <m.icono size={18} aria-hidden="true" /> {m.nombre}
                <ChevronDown size={16} className="flecha" aria-hidden="true" />
              </button>
              {verGrupo &&
                m.tareas.map((t) => (
                  <a key={t.ruta} href={`#/${t.ruta}`} className="riel-sub" aria-current={actual?.ruta === t.ruta ? "page" : undefined}>
                    {t.nombre}
                  </a>
                ))}
            </div>
          );
        })}
        {configuracion.length > 0 && (
          <div className="riel-grupo riel-config">
            <button className="riel-modulo" aria-expanded={abierto("configuracion", enConfiguracion)} onClick={() => alternar("configuracion", enConfiguracion)}>
              <ICONO_CONFIGURACION size={18} aria-hidden="true" /> Configuración
              <ChevronDown size={16} className="flecha" aria-hidden="true" />
            </button>
            {abierto("configuracion", enConfiguracion) && (
              <>
                <a href="#/configuracion" className="riel-sub" aria-current={ruta === "configuracion" ? "page" : undefined}>
                  Ver todo
                </a>
                {AREAS.map((a) => {
                  const del = configuracion.filter((p) => p.area === a.codigo);
                  if (del.length === 0) return null;
                  return (
                    <div key={a.codigo}>
                      <p className="riel-area">{a.nombre}</p>
                      {del.map((p) => (
                        <a key={p.ruta} href={`#/${p.ruta}`} className="riel-sub" aria-current={actual?.ruta === p.ruta ? "page" : undefined}>
                          {p.nombre}
                        </a>
                      ))}
                    </div>
                  );
                })}
              </>
            )}
          </div>
        )}
      </nav>
      <main className="contenido">{pagina}</main>
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
