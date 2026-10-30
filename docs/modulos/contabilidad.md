# Contabilidad base

**Versión:** diseño · **Estado:** en construcción (Semana 3) · Asientos reales: Fase 1 (2027)

## 1. Objetivo

Dar a cada empresa un **plan de cuentas**, **perfiles contables**, **centros de costo** e **impuestos** configurables. Con ellos compras y maestros quedan alineados con la contabilidad desde el inicio. En esta etapa **no se registran asientos**: la orden de compra muestra la vista previa del asiento que se generará en 2027. Decisión: [ADR-004](../adr/0004-base-contable.md).

## 2. Roles y permisos

| Rol estándar | Tipo | Para quién |
| --- | --- | --- |
| `ERP_CNT_ADMINISTRADOR` | administrador | Contador: plan de cuentas, perfiles, impuestos |
| `ERP_CNT_CONFIGURADOR` | configuracion | Analista contable: centros de costo, excepciones de artículos |
| `ERP_CNT_CONSULTA` | consulta | Auditoría, gerencia |

Permisos: `contabilidad.cuenta.ver/editar`, `contabilidad.perfil.ver/editar`, `contabilidad.centro_costo.ver/editar`, `contabilidad.impuesto.ver/editar`.

## 3. Elementos

### Plan de cuentas

| Campo | Regla |
| --- | --- |
| Código | Numérico, único; su prefijo debe ser el de la cuenta padre (`6011` cuelga de `601`) |
| Nombre | Obligatorio |
| Naturaleza | Activo, pasivo, patrimonio, gasto, ingreso, orden (se hereda de la clase) |
| Imputable | Solo las cuentas imputables se usan en perfiles, impuestos y compras |
| Plantilla de origen | `PCGE-2019`, `PCGE-2026`, `propia` |
| Activa | Una cuenta usada no se elimina, solo se desactiva |

### Perfiles contables (precargados en Perú)

| Perfil | Tipo de artículo | Cargo | Destino (Debe ↔ Haber) | Por pagar |
| --- | --- | --- | --- | --- |
| `MERCADERIA` | Bien inventariable | 6011 Mercaderías | 20111 Mercaderías – Costo ↔ 6111\* | 4212 Emitidas |
| `MATERIA_PRIMA` | Bien inventariable | 6021\* | 24111 Materias primas – Costo ↔ 6121\* | 4212 Emitidas |
| `SUMINISTRO_ALMACEN` | Bien inventariable | 6032\* Suministros | 2524 Otros suministros ↔ 6132\* | 4212 Emitidas |
| `CONSUMO_DIRECTO` | Bien no inventariable | 656\* Suministros | — | 4212 Emitidas |
| `SERVICIO` | Servicio | 639\* Otros servicios prestados por terceros | — | 4212 Emitidas |
| `ACTIVO_FIJO` | Activo fijo | 33611 Equipo para procesamiento de información – Costo | — | 4654 Pasivos por compra de PPE |

Códigos de los elementos 2, 3 y 4 verificados contra el catálogo oficial del PCGE Modificado 2019. Los marcados con \* (elemento 6) se tomaron de práctica contable y quedan **por validar**.

!!! warning "Validación contable"
    Los códigos de la plantilla siguen el PCGE Modificado 2019 y los debe revisar un contador antes del primer cliente. Como son configurables, ajustarlos no requiere cambiar código.

### Centros de costo

Código, nombre, unidad de negocio, responsable (opcional), activo. Cada línea de solicitud lleva un centro de costo; por defecto, el del solicitante.

### Impuestos

| Código | Tasa | Cuenta |
| --- | --- | --- |
| `IGV18` | 18 % | 40111 IGV – Cuenta propia |
| `EXO` | 0 % (exonerado) | — |
| `INA` | 0 % (inafecto) | — |

## 4. Vista previa del asiento (orden de compra, Semana 5)

Ejemplo: orden de S/ 1,000 + IGV de suministros para almacén, centro de costo `ADM-01`.

| Cuenta | Centro de costo | Debe | Haber |
| --- | --- | --- | --- |
| 6032 Suministros | ADM-01 | 1,000.00 | |
| 40111 IGV – Cuenta propia | | 180.00 | |
| 4212 Facturas emitidas por pagar | | | 1,180.00 |
| *Destino:* 2524 Otros suministros | | 1,000.00 | |
| *Destino:* 6132 Variación de suministros | | | 1,000.00 |

Se muestra con la etiqueta **"Vista previa — no contabilizado"**. El asiento real se genera en 2027 con la factura del proveedor, usando la misma regla.

## 5. Reglas

- Un perfil solo acepta cuentas imputables y activas, de la naturaleza esperada (cargo en gasto o activo, por pagar en pasivo).
- No se desactiva una cuenta usada por un perfil o impuesto activo.
- Una plantilla nueva (por ejemplo `PCGE-2026`) agrega cuentas; no borra las existentes.
