# Perú (`pe`)

**Moneda funcional:** PEN · **Estado:** plantilla contable base en construcción (Semana 3)

## Plan de cuentas

| Plantilla | Norma | Uso en Victoria ERP |
| --- | --- | --- |
| `PCGE-2019` | PCGE Modificado 2019 (obligatorio desde 2020) | Plantilla por defecto para empresas nuevas |
| `PCGE-2026` | Resolución N.° 002-2026-EF/30, vigente desde el 1 de enero de 2028 | Se agregará como plantilla; mantiene la estructura de 2019 |

La plantilla base de Victoria ERP es un **PCGE reducido** con las cuentas que necesitan compras y los perfiles contables:

| Elemento | Cuentas incluidas |
| --- | --- |
| 1 Activo disponible y exigible | 1673 IGV por acreditar en compras |
| 2 Activo realizable | 20111 Mercaderías – Costo · 24111 Materias primas – Costo · 2524 Otros suministros · 261 Envases · 281 Inventarios por recibir – Mercaderías |
| 3 Activo inmovilizado | 33311 Maquinaria y equipo – Costo · 33511 Muebles – Costo · 33611 Equipo para procesamiento de información – Costo |
| 4 Pasivo | 40111 IGV – Cuenta propia · 4212 Facturas emitidas por pagar · 4654 Pasivos por compra de propiedad, planta y equipo |
| 6 Gastos por naturaleza | 6011, 6021, 6032, 6111, 6121, 6132, 639, 656 (por validar) |

Cada empresa puede agregar subcuentas, desactivar cuentas o cargar su propio plan desde Excel.

## Impuestos

| Código | Descripción | Tasa | Cuenta |
| --- | --- | --- | --- |
| `IGV18` | IGV | 18 % | 40111 |
| `EXO` | Exonerado | 0 % | — |
| `INA` | Inafecto | 0 % | — |

## Pendiente para 2027

Comprobantes electrónicos SUNAT, libros electrónicos (PLE), detracciones, retenciones y percepciones.
