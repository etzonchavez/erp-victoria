import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  api,
  cuentaTexto,
  NOMBRE_TIPO_ARTICULO,
  REGLAS_PERFIL,
  type Cuenta,
  type PerfilContable,
} from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { SelectorEmpresa, SinEmpresa, useEmpresaActiva } from "../empresa";
import { useSesion } from "../sesion";

type Rol = "cargo" | "existencia" | "variacion" | "por_pagar";
const ROLES: { rol: Rol; campo: string; etiqueta: string; ayuda: string }[] = [
  { rol: "cargo", campo: "cuenta_cargo_id", etiqueta: "Cuenta de cargo", ayuda: "Donde se registra la compra (60x, 63x, 65x o 33x)." },
  { rol: "existencia", campo: "cuenta_existencia_id", etiqueta: "Cuenta de existencia", ayuda: "Inventario que aumenta con el ingreso al almacén (20x, 24x, 25x)." },
  { rol: "variacion", campo: "cuenta_variacion_id", etiqueta: "Cuenta de variación", ayuda: "Contrapartida del destino (61x)." },
  { rol: "por_pagar", campo: "cuenta_por_pagar_id", etiqueta: "Cuenta por pagar", ayuda: "Deuda con el proveedor (42x o 46x)." },
];

type Formulario = { codigo: string; nombre: string; tipo_articulo: string; activo: boolean } & Record<string, string | boolean>;
const vacio = (): Formulario => ({
  codigo: "",
  nombre: "",
  tipo_articulo: "bien_no_inventariable",
  activo: true,
  cuenta_cargo_id: "",
  cuenta_existencia_id: "",
  cuenta_variacion_id: "",
  cuenta_por_pagar_id: "",
});

export default function PerfilesContables() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const editar = puede("contabilidad.perfil.editar");
  const { empresas, empresa, elegir, cargando } = useEmpresaActiva();
  const [perfiles, setPerfiles] = useState<PerfilContable[]>([]);
  const [cuentas, setCuentas] = useState<Cuenta[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<PerfilContable | "nuevo" | null>(null);
  const [form, setForm] = useState<Formulario>(vacio);
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    if (!empresa) return;
    setError(null);
    try {
      const [p, c] = await Promise.all([
        api<PerfilContable[]>(`/contabilidad/empresas/${empresa.id}/perfiles`),
        puede("contabilidad.cuenta.ver") ? api<Cuenta[]>(`/contabilidad/empresas/${empresa.id}/cuentas`) : Promise.resolve([]),
      ]);
      setPerfiles(p);
      setCuentas(c);
    } catch (e) {
      setError(e);
    }
  }, [empresa, puede]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const abrir = (p: PerfilContable | "nuevo") => {
    setErrorForm(null);
    setEditando(p);
    setForm(
      p === "nuevo"
        ? vacio()
        : {
            codigo: p.codigo,
            nombre: p.nombre,
            tipo_articulo: p.tipo_articulo,
            activo: p.activo,
            cuenta_cargo_id: p.cuenta_cargo.id,
            cuenta_existencia_id: p.cuenta_existencia?.id ?? "",
            cuenta_variacion_id: p.cuenta_variacion?.id ?? "",
            cuenta_por_pagar_id: p.cuenta_por_pagar.id,
          },
    );
  };
  const cerrar = useCallback(() => setEditando(null), []);
  const nuevo = editando === "nuevo";
  const reglas = REGLAS_PERFIL[form.tipo_articulo];

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    if (!empresa) return;
    setGuardando(true);
    setErrorForm(null);
    const cuentasForm = Object.fromEntries(
      ROLES.map(({ rol, campo }) => [campo, reglas[rol] ? (form[campo] as string) || null : null]),
    );
    try {
      if (nuevo) {
        await api(`/contabilidad/empresas/${empresa.id}/perfiles`, {
          metodo: "POST",
          cuerpo: { codigo: form.codigo, nombre: form.nombre, tipo_articulo: form.tipo_articulo, ...cuentasForm },
        });
        avisar(`Perfil ${form.codigo.toUpperCase()} creado.`);
      } else if (editando) {
        await api(`/contabilidad/perfiles/${editando.id}`, {
          metodo: "PATCH",
          cuerpo: { nombre: form.nombre, activo: form.activo, ...cuentasForm },
        });
        avisar(`Perfil ${editando.codigo} guardado. Aplica a las compras nuevas.`);
      }
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const opciones = (naturalezas: string[]) =>
    cuentas.filter((c) => c.imputable && c.activo && naturalezas.includes(c.naturaleza));

  return (
    <>
      <Encabezado
        titulo="Perfiles contables"
        descripcion="Cada perfil define a qué cuentas va una compra según el tipo de artículo. Las categorías de artículo usan estos perfiles, así quien compra no elige cuentas."
        accion={
          editar && (
            <button className="boton boton-primario" onClick={() => abrir("nuevo")} disabled={!empresa}>
              Crear perfil
            </button>
          )
        }
      />
      <div className="barra-filtros">
        <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={elegir} />
      </div>
      <MensajeError error={error} />
      {!empresa ? (
        <SinEmpresa cargando={cargando} />
      ) : (
        <div className="tabla-contenedor">
          <table className="tabla">
            <thead>
              <tr>
                <th>Perfil</th>
                <th>Tipo de artículo</th>
                <th>Cargo</th>
                <th>Destino (Debe ↔ Haber)</th>
                <th>Por pagar</th>
                <th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {perfiles.map((p) => (
                <tr key={p.id} onClick={() => abrir(p)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrir(p)}>
                  <td>
                    <span className="fuerte">{p.nombre}</span>
                    <p className="tenue">
                      <code>{p.codigo}</code>
                    </p>
                  </td>
                  <td>{NOMBRE_TIPO_ARTICULO[p.tipo_articulo] ?? p.tipo_articulo}</td>
                  <td>{cuentaTexto(p.cuenta_cargo)}</td>
                  <td>
                    {p.cuenta_existencia ? (
                      <>
                        {p.cuenta_existencia.codigo} ↔ {p.cuenta_variacion?.codigo}
                      </>
                    ) : (
                      <span className="tenue">—</span>
                    )}
                  </td>
                  <td>{p.cuenta_por_pagar.codigo}</td>
                  <td>
                    <Estado activo={p.activo} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Panel titulo={nuevo ? "Crear perfil contable" : `Perfil ${form.codigo}`} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          {nuevo && (
            <label>
              Código
              <input
                value={form.codigo}
                maxLength={30}
                required
                placeholder="UTILES_OFICINA"
                onChange={(e) => setForm({ ...form, codigo: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_") })}
              />
            </label>
          )}
          <label>
            Nombre
            <input value={form.nombre} maxLength={100} required disabled={!editar} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </label>
          <label>
            Tipo de artículo
            <select value={form.tipo_articulo} disabled={!nuevo} onChange={(e) => setForm({ ...form, tipo_articulo: e.target.value })}>
              {Object.entries(NOMBRE_TIPO_ARTICULO).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            {!nuevo && <small>El tipo no cambia; crea otro perfil si necesitas uno distinto.</small>}
          </label>
          {ROLES.filter(({ rol }) => reglas[rol]).map(({ rol, campo, etiqueta, ayuda }) => (
            <label key={rol}>
              {etiqueta}
              <select
                value={form[campo] as string}
                required
                disabled={!editar}
                onChange={(e) => setForm({ ...form, [campo]: e.target.value })}
              >
                <option value="">Elegir cuenta…</option>
                {opciones(reglas[rol]!).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.codigo} {c.nombre}
                  </option>
                ))}
              </select>
              <small>{ayuda}</small>
            </label>
          ))}
          {!nuevo && (
            <label className="opcion">
              <input type="checkbox" checked={form.activo} disabled={!editar} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
              <span>
                Perfil activo
                <small>Cambiar cuentas afecta solo a las compras nuevas; las existentes conservan su cuenta.</small>
              </span>
            </label>
          )}
          <MensajeError error={errorForm} />
          {editar && (
            <div className="acciones">
              <button type="button" className="boton" onClick={cerrar}>
                Cancelar
              </button>
              <BotonAccion ocupado={guardando} textoOcupado={nuevo ? "Creando…" : "Guardando…"}>
                {nuevo ? "Crear perfil" : "Guardar cambios"}
              </BotonAccion>
            </div>
          )}
        </form>
      </Panel>
    </>
  );
}
