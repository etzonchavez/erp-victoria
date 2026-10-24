import { useCallback, useEffect, useState } from "react";
import { api, type Modulo } from "../api";
import { Encabezado, Estado, Interruptor, MensajeError } from "../componentes";
import { useSesion } from "../sesion";

export default function Modulos() {
  const { puede, recargar } = useSesion();
  const [modulos, setModulos] = useState<Modulo[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [cambiando, setCambiando] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      setModulos(await api<Modulo[]>("/seguridad/modulos"));
    } catch (e) {
      setError(e);
    }
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const cambiar = async (m: Modulo, activo: boolean) => {
    setError(null);
    setCambiando(m.codigo);
    try {
      await api(`/seguridad/modulos/${m.codigo}`, { metodo: "PATCH", cuerpo: { activo } });
      await Promise.all([cargar(), recargar()]);
    } catch (e) {
      setError(e);
    } finally {
      setCambiando(null);
    }
  };

  return (
    <>
      <Encabezado
        titulo="Módulos"
        descripcion="Activa solo los módulos que tu empresa usa. Un módulo inactivo desaparece del menú y sus permisos dejan de aplicar."
      />
      <MensajeError error={error} />
      <ul className="lista-modulos">
        {modulos.map((m) => (
          <li key={m.codigo}>
            <div>
              <p className="fuerte">{m.nombre}</p>
              <p className="tenue">{m.obligatorio ? "Siempre activo: administra el acceso al ERP." : <code>{m.codigo}</code>}</p>
            </div>
            <Estado activo={m.activo} />
            <Interruptor
              etiqueta={`${m.activo ? "Desactivar" : "Activar"} ${m.nombre}`}
              activo={m.activo}
              deshabilitado={m.obligatorio || !puede("seguridad.modulo.editar") || cambiando === m.codigo}
              onCambio={(v) => cambiar(m, v)}
            />
          </li>
        ))}
      </ul>
    </>
  );
}
