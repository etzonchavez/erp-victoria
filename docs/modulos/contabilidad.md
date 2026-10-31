# Contabilidad base

**Versión:** 0.10.0 · **Estado:** disponible (plan de cuentas, perfiles, centros de costo, impuestos) · Asientos reales: Fase 1 (2027)

## 1. Objetivo

Dar a cada empresa un **plan de cuentas**, **perfiles contables**, **centros de costo** e **impuestos** configurables. Con ellos compras y maestros quedan alineados con la contabilidad desde el inicio. En esta etapa **no se registran asientos**: la orden de compra muestra la vista previa del asiento que se generará en 2027. Decisión: [ADR-004](../adr/0004-base-contable.md).

## 2. Roles y permisos

| Rol estándar | Tipo | Para quién |
| --- | --- | --- |
| `ERP_CNT_ADMINISTRADOR` | administrador | Contador: plan de cuentas, perfiles, impuestos y centros de costo |
| `ERP_CNT_CONFIGURADOR` | configuracion | Analista contable: mantiene los centros de costo y consulta el resto |
| `ERP_CNT_CONSULTA` | consulta | Auditoría, gerencia |

| Permiso | Permite |
| --- | --- |
| `contabilidad.cuenta.ver` / `.editar` | Ver el plan; crear y editar cuentas; cargar la plantilla del país |
| `contabilidad.perfil.ver` / `.editar` | Perfiles contables |
| `contabilidad.centro_costo.ver` / `.editar` | Centros de costo |
| `contabilidad.impuesto.ver` / `.editar` | Impuestos |

El módulo **Contabilidad** se activa en *Administración → Módulos*. Todas las pantallas trabajan sobre una empresa: si hay varias, se elige arriba en cada pantalla y el ERP la recuerda.

## Puesta en marcha

1. Al **crear una empresa** (Maestros → Empresas) se cargan automáticamente su plan de cuentas, los 8 perfiles contables, los impuestos del país y los perfiles sugeridos de las categorías, aunque el módulo Contabilidad esté inactivo.
2. Las empresas creadas antes de la versión 0.7.0 no tienen plan: en **Contabilidad → Plan de cuentas** aparece el botón *Cargar plantilla del país (PCGE)*. Solo funciona si la empresa no tiene cuentas.
3. El contador revisa las cuentas marcadas *por validar*, agrega las subcuentas que use su empresa y crea los centros de costo.

## 3. Elementos

### Plan de cuentas

| Campo | Regla |
| --- | --- |
| Código | Solo dígitos, único en la empresa. El **padre se detecta solo**: la cuenta existente de código más largo que sea su prefijo (`63211` cuelga de `6321`, o de `63` si no existe `632`) |
| Nombre | Obligatorio |
| Naturaleza | Se hereda del padre. Una cuenta de primer nivel la toma del elemento del PCGE (6 = gasto, 4 = pasivo…) |
| Imputable | Automático: una cuenta es imputable mientras no tenga subcuentas. Solo las imputables se usan en perfiles, impuestos y compras |
| Origen | `PCGE-2019` (plantilla) o `Propia` |
| Activa | Las cuentas no se eliminan, solo se desactivan |

Reglas:

- No se crea una subcuenta bajo una cuenta que ya usa un perfil o impuesto (dejaría de ser imputable): primero se reasigna el perfil.
- No se crea una cuenta "intermedia" (ej. `60` si ya existe `601`): las cuentas nuevas se agregan como subcuentas.
- No se desactiva una cuenta usada por un perfil o impuesto, ni una con subcuentas activas.

### Perfiles contables (precargados en Perú)

| Perfil | Tipo de artículo | Cargo | Destino (Debe ↔ Haber) | Por pagar |
| --- | --- | --- | --- | --- |
| `MERCADERIA` | Bien inventariable | 6011 Mercaderías | 20111 Mercaderías – Costo ↔ 6111\* | 4212 Emitidas |
| `MATERIA_PRIMA` | Bien inventariable | 6021\* | 24111 Materias primas – Costo ↔ 6121\* | 4212 Emitidas |
| `SUMINISTRO_ALMACEN` | Bien inventariable | 6032\* Suministros | 2524 Otros suministros ↔ 6132\* | 4212 Emitidas |
| `CONSUMO_DIRECTO` | Bien no inventariable | 656\* Suministros | — | 4212 Emitidas |
| `SERVICIO` | Servicio | 639\* Otros servicios prestados por terceros | — | 4212 Emitidas |
| `ACTIVO_FIJO` | Activo fijo | 33611 Equipo para procesamiento de información – Costo | — | 4654 Pasivos por compra de PPE |
| `ACTIVO_MUEBLES` | Activo fijo | 33511 Muebles – Costo | — | 4654 |
| `ACTIVO_MAQUINARIA` | Activo fijo | 33311 Maquinaria y equipo de explotación – Costo | — | 4654 |

Códigos de los elementos 2, 3 y 4 verificados contra el catálogo oficial del PCGE Modificado 2019. Los marcados con \* (elemento 6) se tomaron de práctica contable y quedan **por validar**.

!!! warning "Validación contable"
    Los códigos de la plantilla siguen el PCGE Modificado 2019 y los debe revisar un contador antes del primer cliente. Como son configurables, ajustarlos no requiere cambiar código.

Validaciones de cada perfil según el tipo de artículo:

| Tipo | Cargo | Existencia y variación | Por pagar |
| --- | --- | --- | --- |
| Bien inventariable | Gasto | Obligatorias: existencia de activo, variación de gasto | Pasivo |
| Bien no inventariable | Gasto | No llevan | Pasivo |
| Servicio | Gasto | No llevan | Pasivo |
| Activo fijo | Activo | No llevan | Pasivo |

Todas las cuentas deben ser imputables, activas y de la misma empresa. El código y el tipo del perfil no cambian; las cuentas sí, y el cambio aplica a las compras nuevas.

### Perfil de cada categoría de artículo

Las categorías de artículo son comunes a todas las empresas ([Maestros](maestros.md#categorias-de-articulo)); cada empresa asigna su perfil contable a cada categoría. Una categoría sin perfil propio hereda el de su categoría padre. Solo quien tiene `contabilidad.perfil.editar` asigna o cambia perfiles, desde **Maestros → Categorías de artículo**. Todo cambio queda en la auditoría con el perfil anterior y el nuevo.

### Excepción contable de un artículo

Un artículo puede usar, en una empresa, un perfil distinto al de su categoría: el contador lo elige en la ficha del artículo (Maestros → Artículos). El perfil debe ser del mismo tipo que el artículo. El orden para encontrar las cuentas de un artículo es: **excepción del artículo → perfil de su categoría → perfil heredado de la categoría padre**.

### Centros de costo

| Campo | Regla |
| --- | --- |
| Código | Mayúsculas, números, `-` o `_`, hasta 20; único en la empresa |
| Nombre | Obligatorio |
| Unidad de negocio | Obligatoria, activa y de la misma empresa |
| Responsable | Opcional |

Cada línea de solicitud llevará un centro de costo (Semana 4).

### Impuestos

| Código | Tasa | Cuenta |
| --- | --- | --- |
| `IGV18` | 18 % | 40111 IGV – Cuenta propia |
| `EXO` | 0 % (exonerado) | — |
| `INA` | 0 % (inafecto) | — |

Un impuesto con tasa mayor a cero necesita una cuenta imputable de pasivo o de activo (por ejemplo 1673 si la empresa registra el IGV por acreditar).

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
