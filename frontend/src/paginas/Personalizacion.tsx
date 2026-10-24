import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { api, NOMBRE_PRODUCTO, type Marca } from "../api";
import { Encabezado, MensajeError } from "../componentes";
import { useSesion } from "../sesion";

const FORMATOS = ["image/png", "image/jpeg", "image/webp"];
const MAXIMO = 500 * 1024;

export default function Personalizacion() {
  const { marca, recargarMarca } = useSesion();
  const [nombre, setNombre] = useState(marca.nombre_empresa ?? "");
  const [error, setError] = useState<unknown>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [trabajando, setTrabajando] = useState(false);
  const entrada = useRef<HTMLInputElement>(null);

  useEffect(() => setNombre(marca.nombre_empresa ?? ""), [marca.nombre_empresa]);

  const ejecutar = async (accion: () => Promise<unknown>, exito: string) => {
    setError(null);
    setAviso(null);
    setTrabajando(true);
    try {
      await accion();
      await recargarMarca();
      setAviso(exito);
    } catch (e) {
      setError(e);
    } finally {
      setTrabajando(false);
    }
  };

  const guardarNombre = (e: FormEvent) => {
    e.preventDefault();
    ejecutar(
      () => api<Marca>("/seguridad/personalizacion", { metodo: "PUT", cuerpo: { nombre_empresa: nombre } }),
      "Nombre de la empresa guardado.",
    );
  };

  const elegirLogo = (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0];
    e.target.value = "";
    if (!archivo) return;
    if (!FORMATOS.includes(archivo.type)) {
      setError(new Error("El logo debe ser una imagen PNG, JPG o WebP."));
      return;
    }
    if (archivo.size > MAXIMO) {
      setError(new Error(`El logo pesa ${Math.round(archivo.size / 1024)} KB; el máximo es 500 KB.`));
      return;
    }
    ejecutar(
      () => api<Marca>("/seguridad/personalizacion/logo", { metodo: "PUT", archivo: { campo: "archivo", valor: archivo } }),
      "Logo actualizado. Ya aparece en el ingreso y en el menú.",
    );
  };

  const quitarLogo = () =>
    ejecutar(() => api<Marca>("/seguridad/personalizacion/logo", { metodo: "DELETE" }), "Logo quitado.");

  return (
    <>
      <Encabezado
        titulo="Personalización"
        descripcion={`El logo y el nombre de tu empresa aparecen en la pantalla de ingreso y en el menú de ${NOMBRE_PRODUCTO}.`}
      />
      <MensajeError error={error} />
      {aviso && (
        <div className="aviso aviso-exito" role="status">
          {aviso}
        </div>
      )}

      <div className="personalizacion">
        <section className="bloque">
          <h2>Logo</h2>
          <div className="logo-vista">
            {marca.logo_url ? (
              <img src={marca.logo_url} alt="Logo actual de la empresa" />
            ) : (
              <p className="tenue">Sin logo. Se mostrará solo el nombre {NOMBRE_PRODUCTO}.</p>
            )}
          </div>
          <p className="tenue">PNG, JPG o WebP de hasta 500 KB. Se ve mejor horizontal y con fondo transparente.</p>
          <input ref={entrada} type="file" accept={FORMATOS.join(",")} onChange={elegirLogo} hidden />
          <div className="acciones-linea">
            <button className="boton boton-primario" disabled={trabajando} onClick={() => entrada.current?.click()}>
              {marca.logo_url ? "Cambiar logo" : "Subir logo"}
            </button>
            {marca.logo_url && (
              <button className="boton" disabled={trabajando} onClick={quitarLogo}>
                Quitar logo
              </button>
            )}
          </div>
        </section>

        <section className="bloque">
          <h2>Nombre de la empresa</h2>
          <form className="formulario" onSubmit={guardarNombre}>
            <label>
              Nombre que verán tus usuarios
              <input value={nombre} maxLength={150} placeholder="Por ejemplo: Distribuidora Andina S.A.C." onChange={(e) => setNombre(e.target.value)} />
            </label>
            <div className="acciones-linea">
              <button className="boton boton-primario" disabled={trabajando || nombre === (marca.nombre_empresa ?? "")}>
                Guardar nombre
              </button>
            </div>
          </form>
        </section>
      </div>
    </>
  );
}
