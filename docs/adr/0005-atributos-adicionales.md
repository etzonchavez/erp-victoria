# ADR-005: Atributos adicionales configurables en los documentos operativos

**Estado:** aprobado · 30 oct 2026

## Contexto

Cada cliente necesita registrar datos propios en sus documentos de compra (número de proyecto, orden de trabajo, fecha de evento, código de licitación…) y que esos datos pasen al siguiente documento del flujo, sin pedir desarrollo a medida. Los ERP corporativos lo resuelven con campos configurables (en Oracle, *descriptive flexfields*).

## Decisión

Todo **documento operativo** de Victoria ERP (solicitud de compra, orden de compra y los que vengan: recepción, factura de proveedor…) reserva **30 atributos por nivel**:

| Tipo | Cantidad | Columnas |
| --- | --- | --- |
| Texto (hasta 240 caracteres) | 10 | `atr_texto_01` … `atr_texto_10` |
| Número (18 dígitos, 4 decimales) | 10 | `atr_numero_01` … `atr_numero_10` |
| Fecha | 10 | `atr_fecha_01` … `atr_fecha_10` |

Los **niveles** son:

- **Cabecera:** datos de todo el documento.
- **Línea:** datos de cada artículo pedido.
- **Distribución:** datos de cada reparto de una línea entre centros de costo y cuentas.

Reglas:

1. La **configuración es una sola para el grupo**: el atributo "N.° de proyecto" significa lo mismo en todas las empresas.
2. Vienen todos **inactivos**. El administrador activa los que necesita y define para cada uno: **nombre** (obligatorio), **texto de ayuda**, **valor por defecto** y, en los de texto, una **lista de valores** para elegir en vez de escribir.
3. **Copia entre documentos con mapeo configurable:** para cada atributo, el administrador indica a qué atributo del documento siguiente va (del mismo tipo y nivel), o que no se copie. Ejemplo: *Texto 3 de la línea de la solicitud → Texto 1 de la línea de la orden de compra*. Dos atributos no pueden ir al mismo destino.
4. Los valores se validan en el servidor: solo atributos activos, del tipo correcto y, si tienen lista, con un valor de la lista.
5. Los atributos se guardan en **columnas reales** del documento (no en un JSON), así los reportes y el constructor de reportes los filtran y suman como cualquier otro campo.

## Cómo lo usa un módulo nuevo

- Las tablas de cabecera, línea y distribución heredan `ConAtributos` (`app/core/atributos.py`), que agrega las 30 columnas; la migración las crea con `columnas_atributos()`.
- El documento se registra en `DOCUMENTOS` y su flujo en `FLUJOS` (ej. `solicitud → orden_compra`).
- Al crear o editar, el servicio llama `validar_valores(documento, nivel, valores)`; al generar el documento siguiente, `copiar_valores(origen, destino, nivel, valores)`.
- En pantalla, el componente `CamposAtributos` dibuja solo los atributos activos de ese documento y nivel.

## Consecuencias

- Un cliente se adapta sin desarrollo: activa y nombra atributos en *Administración → Atributos adicionales*.
- Costo: 30 columnas por tabla de documento (vacías no ocupan espacio en PostgreSQL).
- El límite de 10 por tipo y nivel es fijo; ampliarlo exige una migración.
- No hay atributos obligatorios en esta versión (decisión de Et); se puede agregar después sin cambiar el modelo.

## Alternativas descartadas

- **JSON libre por documento:** flexible, pero difícil de reportar, validar e indexar.
- **Tabla clave-valor (EAV):** consultas lentas y reportes complejos.
- **Configuración por empresa:** el mismo campo significaría cosas distintas según la empresa y los reportes consolidados perderían sentido.
