import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { api, NOMBRE_PRODUCTO, type Marca } from "../api";
import { BotonAccion, Encabezado, MensajeError, useConfirmacion } from "../componentes";
import { useAvisos } from "../avisos";
import { useSesion } from "../sesion";

const FORMATOS = ["image/png", "image/jpeg", "image/webp"];
const MAXIMO_MB = 2;
const MAXIMO = MAXIMO_MB * 1024 * 1024;
/** Ancho mínimo recomendado para que el logo se vea nítido en pantallas de alta densidad. */
export const ANCHO_RECOMENDADO = 600;

const anchoDeImagen = (archivo: File) =>
  new Promise<number | null>((resolver) => {
    const url = URL.createObjectURL(archivo);
    const img = new Image();
    img.onload = () => {
      resolver(img.naturalWidth);
      URL.revokeObjectURL(url);
    };
    img.onerror = () => {
      resolver(null);
      URL.revokeObjectURL(url);
    };
    img.src = url;
  });

export default function Personalizacion() {
  const { marca, recargarMarca } = useSesion();
  const [nombre, setNombre] = useState(marca.nombre_empresa ?? "");
  const [error, setError] = useState<unknown>(null);
  const [advertencia, setAdvertencia] = useState<string | null>(null);
  const [trabajando, setTrabajando] = useState<"logo" | "quitar" | "nombre" | null>(null);
  const entrada = useRef<HTMLInputElement>(null);
  const { avisar } = useAvisos();
  const nombreGuardado = useConfirmacion();
  const [textoListo, setTextoListo] = useState("Guardado");

  useEffect(() => setNombre(marca.nombre_empresa ?? ""), [marca.nombre_empresa]);

  const ejecutar = async (
    que: "logo" | "quitar" | "nombre",
    accion: () => Promise<unknown>,
    exito: string,
  ): Promise<boolean> => {
    setError(null);
    setTrabajando(que);
    try {
      await accion();
      await recargarMarca();
      avisar(exito);
      return true;
    } catch (e) {
      setError(e);
      return false;
    } finally {
      setTrabajando(null);
    }
  };

  const sinCambios = nombre.trim() === (marca.nombre_empresa ?? "");

  const guardarNombre = async (e: FormEvent) => {
    e.preventDefault();
    if (sinCambios) {
      setTextoListo("Sin cambios por guardar");
      nombreGuardado.confirmar();
      return;
    }
    const ok = await ejecutar(
      "nombre",
      () => api<Marca>("/seguridad/personalizacion", { metodo: "PUT", cuerpo: { nombre_empresa: nombre.trim() } }),
      "Nombre de la empresa guardado.",
    );
    if (ok) {
      setTextoListo("Guardado");
      nombreGuardado.confirmar();
    }
  };

  const elegirLogo = async (e: ChangeEvent<HTMLInputElement>) => {
    const archivo = e.target.files?.[0];
    e.target.value = "";
    if (!archivo) return;
    if (!FORMATOS.includes(archivo.type)) {
      setError(new Error("El logo debe ser una imagen PNG, JPG o WebP."));
      return;
    }
    if (archivo.size > MAXIMO) {
      const mb = (archivo.size / 1024 / 1024).toFixed(1);
      setError(new Error(`El logo pesa ${mb} MB; el máximo es ${MAXIMO_MB} MB.`));
      return;
    }
    const ancho = await anchoDeImagen(archivo);
    setAdvertencia(
      ancho !== null && ancho < ANCHO_RECOMENDADO
        ? `Tu logo mide ${ancho} px de ancho y podría verse borroso. Para que se vea nítido usa una imagen de al menos ${ANCHO_RECOMENDADO} px de ancho.`
        : null,
    );
    ejecutar(
      "logo",
      () => api<Marca>("/seguridad/personalizacion/logo", { metodo: "PUT", archivo: { campo: "archivo", valor: archivo } }),
      "Logo actualizado. Ya aparece en el ingreso y en el menú.",
    );
  };

  const quitarLogo = () =>
    ejecutar("quitar", () => api<Marca>("/seguridad/personalizacion/logo", { metodo: "DELETE" }), "Logo quitado.").then(
      (ok) => ok && setAdvertencia(null),
    );

  return (
    <>
      <Encabezado
        titulo="Personalización"
        descripcion={`El logo y el nombre de tu empresa aparecen en la pantalla de ingreso y en el menú de ${NOMBRE_PRODUCTO}.`}
      />
      <MensajeError error={error} />

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
          {advertencia && (
            <div className="aviso aviso-advertencia" role="alert">
              {advertencia}
            </div>
          )}
          <p className="tenue">
            PNG, JPG o WebP de hasta {MAXIMO_MB} MB. Recomendado: horizontal, con fondo transparente y de al menos{" "}
            {ANCHO_RECOMENDADO} px de ancho.
          </p>
          <input ref={entrada} type="file" accept={FORMATOS.join(",")} onChange={elegirLogo} hidden />
          <div className="acciones-linea">
            <BotonAccion
              type="button"
              ocupado={trabajando === "logo"}
              textoOcupado="Subiendo logo…"
              disabled={trabajando === "quitar"}
              onClick={() => entrada.current?.click()}
            >
              {marca.logo_url ? "Cambiar logo" : "Subir logo"}
            </BotonAccion>
            {marca.logo_url && (
              <BotonAccion
                type="button"
                primario={false}
                ocupado={trabajando === "quitar"}
                textoOcupado="Quitando…"
                disabled={trabajando === "logo"}
                onClick={quitarLogo}
              >
                Quitar logo
              </BotonAccion>
            )}
          </div>
        </section>

        <section className="bloque">
          <h2>Nombre de la empresa</h2>
          <form className="formulario" onSubmit={guardarNombre}>
            <label>
              Nombre que verán tus usuarios
              <input value={nombre} maxLength={150} placeholder="Por ejemplo: Distribuidora Andina S.A.C." onChange={(e) => {
                  setNombre(e.target.value);
                  nombreGuardado.reiniciar();
                }}
              />
            </label>
            <div className="acciones-linea">
              <BotonAccion
                ocupado={trabajando === "nombre"}
                listo={nombreGuardado.listo}
                textoListo={textoListo}
              >
                Guardar nombre
              </BotonAccion>
            </div>
          </form>
        </section>
      </div>
    </>
  );
}
