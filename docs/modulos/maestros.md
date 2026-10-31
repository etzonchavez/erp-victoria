# Maestros

**Versión:** 0.6.0 · **Estado:** empresas, monedas, tipo de cambio y unidades disponibles; categorías, artículos y proveedores en construcción (Semana 3)

## 1. Objetivo del módulo

Registra los datos base que usan todos los procesos: empresa, unidades de negocio, monedas, unidades de medida, proveedores, categorías y artículos. Las categorías y artículos quedan **alineados con la contabilidad base** ([ADR-004](../adr/0004-base-contable.md)), así cada compra sabe a qué cuenta va sin que el usuario elija cuentas.

## 2. Roles y permisos

| Rol estándar | Tipo | Para quién |
| --- | --- | --- |
| `ERP_MAE_ADMINISTRADOR` | administrador | Responsable de datos maestros |
| `ERP_MAE_CONFIGURADOR` | configuracion | Configura empresas, unidades de negocio, monedas y unidades de medida |
| `ERP_MAE_ANALISTA` | operativo | Registra el tipo de cambio diario; más adelante, proveedores y artículos |
| `ERP_MAE_CONSULTA` | consulta | Solo consulta |

| Permiso | Permite |
| --- | --- |
| `maestros.empresa.ver` / `.editar` | Empresas y unidades de negocio |
| `maestros.moneda.ver` / `.editar` | Ver monedas y tipos de cambio / activar y editar monedas |
| `maestros.tipo_cambio.registrar` | Registrar o corregir el tipo de cambio de una fecha |
| `maestros.unidad.ver` / `.editar` | Unidades de medida y conversiones generales |
| `maestros.proveedor.ver` / `.crear` / `.editar` | Proveedores |
| `maestros.categoria.ver` / `.editar` | Árbol de categorías y su perfil contable |
| `maestros.articulo.ver` / `.crear` / `.editar` | Artículos |
| `maestros.articulo.excepcion_contable` | Asignar a un artículo un perfil distinto al de su categoría (solo roles contables) |
| `maestros.importacion.ejecutar` | Carga desde Excel |

## 3. Flujo de configuración

1. **Empresa** → datos legales (RUC, razón social, país, moneda funcional).
2. Al guardar la empresa se carga la **plantilla contable del país**: plan de cuentas, 6 perfiles contables e impuestos (ver [Contabilidad base](contabilidad.md)).
3. **Unidades de negocio** y sus **centros de costo**.
4. **Monedas** y **unidades de medida** (vienen precargadas; se activan las que se usan).
5. **Categorías** → árbol de hasta 3 niveles; cada rama apunta a un perfil contable.
6. **Artículos** → eligen tipo y categoría; las cuentas se resuelven solas.
7. **Proveedores**.

## 4. Pantallas y campos

### Categorías

| Campo | Regla |
| --- | --- |
| Código | Obligatorio, único, mayúsculas (ej. `SUM-OFI`) |
| Nombre | Obligatorio |
| Categoría padre | Opcional; máximo 3 niveles |
| Perfil contable | Opcional en subcategorías (hereda del padre); obligatorio en el primer nivel |
| Activa | Una categoría inactiva no admite artículos nuevos |

La pantalla muestra el árbol y, en cada categoría, el **perfil efectivo** y su origen ("propio" o "heredado de Suministros").

### Artículos

| Campo | Regla |
| --- | --- |
| Código | Obligatorio, único |
| Descripción | Obligatoria, hasta 240 caracteres |
| Tipo | Bien inventariable · Bien no inventariable · Servicio · Activo fijo |
| Categoría | Obligatoria; debe resolver un perfil del mismo tipo |
| Unidad de medida | Obligatoria (servicios: `SRV` por defecto) |
| Impuesto | Por defecto IGV 18 % |
| Perfil contable (excepción) | Solo con permiso `excepcion_contable` |
| Activo | Un artículo inactivo no se puede pedir |

En la ficha del artículo se muestra, solo para lectura, la **combinación contable resultante** (cuenta de cargo, impuesto, cuenta por pagar).

### Empresas

Una instalación de Victoria ERP puede tener **varias empresas legales** (por ejemplo, un grupo con tres RUC).

| Campo | Regla |
| --- | --- |
| País | Solo países con localización disponible (hoy: Perú) |
| RUC | 11 dígitos, prefijo 10, 15, 16, 17 o 20 y dígito verificador válido (algoritmo SUNAT); único por país. **No se puede cambiar** |
| Razón social | Obligatoria, hasta 200 caracteres |
| Nombre comercial | Opcional |
| Dirección fiscal | Opcional |
| Moneda funcional | Por defecto la del país (PEN). **No se puede cambiar**: la contabilidad se lleva en esa moneda |
| Activa | Una empresa inactiva no opera |

Al crear una empresa se crea su unidad de negocio **Principal** y se carga su **plan de cuentas** con perfiles e impuestos del país ([Contabilidad base](contabilidad.md)), para que pueda operar de inmediato.

### Unidades de negocio

Sedes, divisiones o líneas de negocio de una empresa. Se administran dentro de la ficha de la empresa.

| Campo | Regla |
| --- | --- |
| Código | Mayúsculas, números, `-` o `_`, hasta 20; único dentro de la empresa; no cambia |
| Nombre | Obligatorio |
| Activa | La empresa siempre conserva al menos una unidad activa |

### Monedas y tipo de cambio

- Vienen precargadas PEN y USD (activas) y EUR, COP, PAB y CLP (inactivas). Se pueden agregar otras con su código ISO 4217.
- No se desactiva una moneda que sea la moneda funcional de una empresa activa.
- **Tipo de cambio:** un registro por moneda, moneda base y fecha, con precio de **compra** y **venta** (hasta 6 decimales).
    - No se registran fechas futuras y la venta no puede ser menor que la compra.
    - Registrar otra vez la misma fecha **corrige** el valor y queda en la auditoría.
    - Si una fecha no tiene registro (fin de semana o feriado), el ERP usa el **último tipo de cambio anterior**.
- La carga automática desde la SBS o SUNAT está prevista para 2027.

### Unidades de medida

| Campo | Regla |
| --- | --- |
| Código interno | Mayúsculas y números, hasta 10 (ej. `UND`, `CJA`); no cambia |
| Nombre | Obligatorio |
| Código SUNAT | Código del Catálogo N.° 03 de SUNAT (UN/ECE Rec. 20), 2 o 3 caracteres (ej. `NIU`, `KGM`, `ZZ`). Se usará en los comprobantes electrónicos |
| Tipo | Cantidad, servicio, peso, volumen, longitud, área o tiempo |

Vienen precargadas 20 unidades de uso común. **Conversiones generales** (1 KG = 1000 G, 1 DOC = 12 UND…): solo entre unidades del mismo tipo y una sola por par de unidades (la inversa se calcula). Las conversiones propias de un artículo (1 CAJA = 12 UND) se definen en el artículo.

### Proveedores

Se detallan al construirlos (Semana 3, tarea 4).

## 5. Reglas de negocio

- Un artículo no se guarda si su perfil no se resuelve o si el tipo del perfil no coincide con el del artículo.
- Cambiar el perfil de una categoría afecta a las **compras nuevas**; las líneas ya creadas conservan la cuenta que guardaron.
- No se puede eliminar una categoría con artículos ni con subcategorías; solo desactivarla.
- Todo cambio queda en la auditoría.

## 6. Pendiente

- Restringir el acceso de cada usuario a determinadas empresas y unidades de negocio (hoy ve todas).

## 7. Reportes

- Artículos por categoría con su combinación contable (exportable a Excel).

## 8. Configuración por país

La plantilla contable, los impuestos y las unidades de medida precargadas vienen del paquete del país. Perú: [plantilla PCGE](../paises/peru.md).

## 9. Preguntas frecuentes

**¿El usuario de compras tiene que saber de cuentas contables?** No. Elige el artículo; la cuenta sale de la categoría.

**Hoy es feriado y no hay tipo de cambio, ¿qué pasa?** El ERP toma el último registrado antes de esa fecha.

**¿Puedo cambiar el RUC de una empresa mal registrada?** No. Desactívala y crea la empresa correcta; así la auditoría conserva la historia.

**¿Qué pasa cuando entre en vigencia el PCGE 2026?** Se agrega la plantilla `PCGE-2026` y el contador reasigna las cuentas de los perfiles; artículos y categorías no cambian.
