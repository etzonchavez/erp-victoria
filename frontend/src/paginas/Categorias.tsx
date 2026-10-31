import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { api, NOMBRE_TIPO_ARTICULO, type Categoria, type CategoriaPerfil, type PerfilContable } from "../api";
import { useAvisos } from "../avisos";
import { BotonAccion, Encabezado, Estado, MensajeError, Panel } from "../componentes";
import { SelectorEmpresa, useEmpresaActiva } from "../empresa";
import { useSesion } from "../sesion";

const NIVELES = 3;
type Formulario = { codigo: string; nombre: string; padre_id: string; activo: boolean; perfil_id: string };

export default function Categorias() {
  const { puede } = useSesion();
  const { avisar } = useAvisos();
  const editarArbol = puede("maestros.categoria.editar");
  const verPerfil = puede("contabilidad.perfil.ver");
  const editarPerfil = puede("contabilidad.perfil.editar");
  const { empresas, empresa, elegir } = useEmpresaActiva();
  const [categorias, setCategorias] = useState<Categoria[]>([]);
  const [perfilesCat, setPerfilesCat] = useState<Map<string, CategoriaPerfil>>(new Map());
  const [perfiles, setPerfiles] = useState<PerfilContable[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [editando, setEditando] = useState<Categoria | "nueva" | null>(null);
  const [form, setForm] = useState<Formulario>({ codigo: "", nombre: "", padre_id: "", activo: true, perfil_id: "" });
  const [errorForm, setErrorForm] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);
  const [aplicando, setAplicando] = useState(false);
  const [verInactivas, setVerInactivas] = useState(false);

  const cargar = useCallback(async () => {
    setError(null);
    try {
      setCategorias(await api<Categoria[]>("/maestros/categorias"));
      if (verPerfil && empresa) {
        const [filas, p] = await Promise.all([
          api<CategoriaPerfil[]>(`/contabilidad/empresas/${empresa.id}/categorias`),
          api<PerfilContable[]>(`/contabilidad/empresas/${empresa.id}/perfiles`),
        ]);
        setPerfilesCat(new Map(filas.map((f) => [f.categoria_id, f])));
        setPerfiles(p);
      }
    } catch (e) {
      setError(e);
    }
  }, [verPerfil, empresa]);
  useEffect(() => {
    cargar();
  }, [cargar]);

  const porId = useMemo(() => new Map(categorias.map((c) => [c.id, c])), [categorias]);
  const visibles = categorias.filter((c) => verInactivas || c.activo);
  const sinPerfil = verPerfil ? categorias.filter((c) => c.activo && !perfilesCat.get(c.id)?.perfil_efectivo) : [];

  const abrir = (c: Categoria | "nueva", padre?: Categoria) => {
    setErrorForm(null);
    setEditando(c);
    setForm(
      c === "nueva"
        ? { codigo: padre ? `${padre.codigo}-` : "", nombre: "", padre_id: padre?.id ?? "", activo: true, perfil_id: "" }
        : { codigo: c.codigo, nombre: c.nombre, padre_id: c.padre_id ?? "", activo: c.activo, perfil_id: perfilesCat.get(c.id)?.perfil_propio?.id ?? "" },
    );
  };
  const cerrar = useCallback(() => setEditando(null), []);
  const nueva = editando === "nueva";

  // Padres posibles: activas, sin superar 3 niveles, y nunca la propia categoría o sus subcategorías.
  const padresPosibles = useMemo(() => {
    if (!editando) return [];
    const propia = editando === "nueva" ? null : editando;
    const excluir = new Set<string>();
    if (propia) {
      excluir.add(propia.id);
      let cambio = true;
      while (cambio) {
        cambio = false;
        for (const c of categorias)
          if (c.padre_id && excluir.has(c.padre_id) && !excluir.has(c.id)) {
            excluir.add(c.id);
            cambio = true;
          }
      }
    }
    const altura = propia ? 1 + Math.max(0, ...categorias.filter((c) => excluir.has(c.id)).map((c) => c.nivel - propia.nivel)) : 1;
    return categorias.filter((c) => c.activo && !excluir.has(c.id) && c.nivel + altura <= NIVELES);
  }, [editando, categorias]);

  const padreElegido = form.padre_id ? porId.get(form.padre_id) : undefined;
  const filaActual = editando && editando !== "nueva" ? perfilesCat.get(editando.id) : undefined;
  // Lo que heredaría si no tuviera perfil propio: el efectivo del padre.
  const heredaria = padreElegido ? perfilesCat.get(padreElegido.id)?.perfil_efectivo : null;

  const guardar = async (e: FormEvent) => {
    e.preventDefault();
    setGuardando(true);
    setErrorForm(null);
    try {
      let id = editando !== "nueva" && editando ? editando.id : "";
      if (nueva) {
        const creada = await api<Categoria>("/maestros/categorias", {
          metodo: "POST",
          cuerpo: { codigo: form.codigo, nombre: form.nombre, padre_id: form.padre_id || null },
        });
        id = creada.id;
      } else if (editando && editarArbol) {
        await api(`/maestros/categorias/${editando.id}`, {
          metodo: "PATCH",
          cuerpo: { nombre: form.nombre, padre_id: form.padre_id || null, activo: form.activo },
        });
      }
      const perfilAntes = filaActual?.perfil_propio?.id ?? "";
      if (editarPerfil && empresa && form.perfil_id !== perfilAntes) {
        await api(`/contabilidad/empresas/${empresa.id}/categorias/${id}/perfil`, {
          metodo: "PUT",
          cuerpo: { perfil_id: form.perfil_id || null },
        });
      }
      avisar(nueva ? `Categoría ${form.codigo.toUpperCase()} creada.` : `Categoría ${form.codigo} guardada.`);
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(err);
    } finally {
      setGuardando(false);
    }
  };

  const aplicarSugeridos = async () => {
    if (!empresa) return;
    setAplicando(true);
    setError(null);
    try {
      const r = await api<{ perfiles: number; categorias: number }>(`/contabilidad/empresas/${empresa.id}/sugeridos`, {
        metodo: "POST",
      });
      avisar(
        r.perfiles || r.categorias
          ? `Listo: ${r.perfiles} perfiles creados y ${r.categorias} categorías con perfil asignado.`
          : "Todo estaba completo; no se cambió nada.",
      );
      await cargar();
    } catch (err) {
      setError(err);
    } finally {
      setAplicando(false);
    }
  };

  const celdaPerfil = (c: Categoria) => {
    const f = perfilesCat.get(c.id);
    if (!f?.perfil_efectivo) return <span className="etiqueta etiqueta-alerta">Sin perfil</span>;
    return (
      <>
        {f.perfil_efectivo.nombre}
        <p className="tenue">{f.heredado_de ? `Heredado de ${f.heredado_de.nombre}` : NOMBRE_TIPO_ARTICULO[f.perfil_efectivo.tipo_articulo]}</p>
      </>
    );
  };

  return (
    <>
      <Encabezado
        titulo="Categorías de artículo"
        descripcion="Árbol de hasta 3 niveles, común a todas las empresas. Cada categoría lleva un perfil contable por empresa; las subcategorías sin perfil propio heredan el de su categoría padre."
        accion={
          editarArbol && (
            <button className="boton boton-primario" onClick={() => abrir("nueva")}>
              Crear categoría
            </button>
          )
        }
      />
      <div className="barra-filtros">
        {verPerfil ? <SelectorEmpresa empresas={empresas} empresa={empresa} elegir={elegir} /> : <span />}
        <label className="filtro">
          <input type="checkbox" checked={verInactivas} onChange={(e) => setVerInactivas(e.target.checked)} /> Mostrar inactivas
        </label>
      </div>
      <MensajeError error={error} />
      {verPerfil && empresa && sinPerfil.length > 0 && (
        <div className="aviso aviso-advertencia aviso-con-accion">
          <p>
            {sinPerfil.length === 1 ? "1 categoría activa no tiene" : `${sinPerfil.length} categorías activas no tienen`} perfil
            contable en {empresa.razon_social}: sus artículos no podrán comprarse hasta asignarle uno.
          </p>
          {editarPerfil && (
            <BotonAccion primario={false} ocupado={aplicando} textoOcupado="Aplicando…" onClick={aplicarSugeridos}>
              Aplicar perfiles sugeridos
            </BotonAccion>
          )}
        </div>
      )}
      <div className="tabla-contenedor">
        <table className="tabla">
          <thead>
            <tr>
              <th>Categoría</th>
              {verPerfil && <th>Perfil contable{empresa && empresas.length > 1 ? ` (${empresa.razon_social})` : ""}</th>}
              <th>Estado</th>
              {editarArbol && <th />}
            </tr>
          </thead>
          <tbody>
            {visibles.map((c) => (
              <tr key={c.id} className={c.nivel === 1 ? "fila-titulo" : undefined} onClick={() => abrir(c)} tabIndex={0} onKeyDown={(k) => k.key === "Enter" && abrir(c)}>
                <td style={{ paddingLeft: 16 + (c.nivel - 1) * 24 }}>
                  <span className="codigo-cuenta">{c.codigo}</span> {c.nombre}
                </td>
                {verPerfil && <td>{celdaPerfil(c)}</td>}
                <td>
                  <Estado activo={c.activo} si="Activa" no="Inactiva" />
                </td>
                {editarArbol && (
                  <td className="celda-accion">
                    {c.nivel < NIVELES && c.activo && (
                      <button
                        className="enlace"
                        onClick={(e) => {
                          e.stopPropagation();
                          abrir("nueva", c);
                        }}
                      >
                        + Subcategoría
                      </button>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Panel titulo={nueva ? "Crear categoría" : `Categoría ${form.codigo}`} abierto={editando !== null} onCerrar={cerrar}>
        <form className="formulario" onSubmit={guardar}>
          <label>
            Código
            <input
              value={form.codigo}
              maxLength={20}
              required
              disabled={!nueva}
              placeholder="SUM-OFI"
              onChange={(e) => setForm({ ...form, codigo: e.target.value.toUpperCase().replace(/\s/g, "-") })}
            />
            {!nueva && <small>El código no cambia.</small>}
          </label>
          <label>
            Nombre
            <input value={form.nombre} maxLength={120} required disabled={!editarArbol} onChange={(e) => setForm({ ...form, nombre: e.target.value })} />
          </label>
          <label>
            Categoría padre
            <select value={form.padre_id} disabled={!editarArbol} onChange={(e) => setForm({ ...form, padre_id: e.target.value })}>
              <option value="">— Ninguna (primer nivel) —</option>
              {padresPosibles.map((p) => (
                <option key={p.id} value={p.id}>
                  {"  ".repeat(p.nivel - 1)}
                  {p.codigo} · {p.nombre}
                </option>
              ))}
            </select>
            <small>Máximo {NIVELES} niveles. Al mover una categoría se mueven también sus subcategorías.</small>
          </label>

          {verPerfil && empresa && (
            <fieldset>
              <legend>Perfil contable en {empresa.razon_social}</legend>
              <label>
                Perfil
                <select value={form.perfil_id} disabled={!editarPerfil} onChange={(e) => setForm({ ...form, perfil_id: e.target.value })}>
                  <option value="">
                    {padreElegido
                      ? `Heredar de ${padreElegido.nombre}${heredaria ? ` (${heredaria.nombre})` : " (sin perfil)"}`
                      : "Sin perfil"}
                  </option>
                  {perfiles
                    .filter((p) => p.activo)
                    .map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.nombre} — {NOMBRE_TIPO_ARTICULO[p.tipo_articulo]}
                      </option>
                    ))}
                </select>
                <small>
                  {editarPerfil
                    ? "Define a qué cuentas van las compras de esta categoría. Cambiarlo afecta solo a las compras nuevas."
                    : "Solo el contador asigna el perfil contable."}
                </small>
              </label>
            </fieldset>
          )}

          {!nueva && editarArbol && (
            <label className="opcion">
              <input type="checkbox" checked={form.activo} onChange={(e) => setForm({ ...form, activo: e.target.checked })} />
              <span>
                Categoría activa
                <small>Para desactivarla, desactiva primero sus subcategorías.</small>
              </span>
            </label>
          )}
          <MensajeError error={errorForm} />
          {(editarArbol || editarPerfil) && (
            <div className="acciones">
              <button type="button" className="boton" onClick={cerrar}>
                Cancelar
              </button>
              <BotonAccion ocupado={guardando} textoOcupado={nueva ? "Creando…" : "Guardando…"} disabled={nueva && !editarArbol}>
                {nueva ? "Crear categoría" : "Guardar cambios"}
              </BotonAccion>
            </div>
          )}
        </form>
      </Panel>
    </>
  );
}
