# Maestros

**Versión:** 0.10.0 · **Estado:** disponible (empresas, monedas, tipo de cambio, unidades, categorías, proveedores y artículos); carga desde Excel pendiente

## 1. Objetivo del módulo

Registra los datos base que usan todos los procesos: empresa, unidades de negocio, monedas, unidades de medida, proveedores, categorías y artículos. Las categorías y artículos quedan **alineados con la contabilidad base** ([ADR-004](../adr/0004-base-contable.md)), así cada compra sabe a qué cuenta va sin que el usuario elija cuentas.

## 2. Roles y permisos

| Rol estándar | Tipo | Para quién |
| --- | --- | --- |
| `ERP_MAE_ADMINISTRADOR` | administrador | Responsable de datos maestros |
| `ERP_MAE_CONFIGURADOR` | configuracion | Configura empresas, unidades de negocio, monedas y unidades de medida |
| `ERP_MAE_ANALISTA` | operativo | Registra artículos, proveedores y el tipo de cambio diario |
| `ERP_MAE_CONSULTA` | consulta | Solo consulta |

| Permiso | Permite |
| --- | --- |
| `maestros.empresa.ver` / `.editar` | Empresas y unidades de negocio |
| `maestros.moneda.ver` / `.editar` | Ver monedas y tipos de cambio / activar y editar monedas |
| `maestros.tipo_cambio.registrar` | Registrar o corregir el tipo de cambio de una fecha |
| `maestros.unidad.ver` / `.editar` | Unidades de medida y conversiones generales |
| `maestros.proveedor.ver` / `.crear` / `.editar` | Ver (cuentas bancarias enmascaradas) / registrar / editar proveedores, sus contactos y categorías, y bloquearlos por empresa |
| `maestros.proveedor.banco` | Ver completas, registrar y desactivar las cuentas bancarias de los proveedores. **No viene en ningún rol estándar salvo el administrador de maestros**: asígnalo solo a tesorería |
| `maestros.condicion_pago.editar` | Condiciones de pago |
| `maestros.categoria.ver` / `.editar` | Ver / crear, mover y editar el árbol de categorías (el perfil contable lo asigna Contabilidad) |
| `maestros.articulo.ver` / `.crear` / `.editar` | Ver artículos y su configuración contable por empresa / registrarlos / editarlos con sus unidades alternativas |
| `maestros.importacion.ejecutar` | Carga desde Excel |

## 3. Flujo de configuración

1. **Empresa** → datos legales (RUC, razón social, país, moneda funcional).
2. Al guardar la empresa se carga la **plantilla contable del país**: plan de cuentas, 8 perfiles contables, impuestos y perfiles sugeridos para las categorías de ejemplo (ver [Contabilidad base](contabilidad.md)).
3. **Unidades de negocio** y sus **centros de costo**.
4. **Monedas** y **unidades de medida** (vienen precargadas; se activan las que se usan).
5. **Categorías** → árbol de hasta 3 niveles, común a todas las empresas; Contabilidad asigna a cada rama un perfil contable por empresa.
6. **Artículos** → eligen tipo y categoría; las cuentas se resuelven solas.
7. **Proveedores**.

## 4. Pantallas y campos

### Categorías de artículo

El árbol es **compartido por todas las empresas** de la instalación, así un artículo se registra una sola vez. Lo que cambia por empresa es el **perfil contable** de cada categoría.

| Campo | Regla | Quién lo cambia |
| --- | --- | --- |
| Código | Mayúsculas, números, `-` o `_`, hasta 20; único; no cambia | Maestros |
| Nombre | Obligatorio | Maestros |
| Categoría padre | Opcional; máximo **3 niveles**. Al mover una categoría se mueve con sus subcategorías; no puede quedar dentro de sí misma | Maestros |
| Perfil contable (por empresa) | Opcional: si una categoría no tiene perfil propio, **hereda** el de su categoría padre | Contabilidad (`contabilidad.perfil.editar`) |
| Activa | Para desactivar una categoría, primero se desactivan sus subcategorías | Maestros |

La pantalla muestra el árbol y, para la empresa elegida, el **perfil efectivo** de cada categoría y si es propio o "heredado de…". Si alguna categoría activa no tiene perfil, aparece un aviso: sus artículos no podrán comprarse hasta asignarle uno.

**Categorías de ejemplo.** Toda instalación trae un árbol inicial que se puede renombrar, desactivar o ampliar:

| Categoría | Subcategorías | Perfil sugerido (Perú) |
| --- | --- | --- |
| MER Mercaderías | — | Mercaderías |
| MP Materias primas | — | Materias primas |
| SUM Suministros | REP Repuestos (hereda) · OFI Útiles de oficina · LIM Limpieza | Suministros de almacén; OFI y LIM: Consumo directo |
| SRV Servicios | MAN Mantenimiento · CON Consultoría · TRA Transporte (heredan) | Servicios de terceros |
| AF Activo fijo | TI Cómputo (hereda) · MUE Muebles · MAQ Maquinaria | Activo fijo – cómputo / muebles / maquinaria |

Al crear una empresa se asignan los perfiles sugeridos. Para empresas creadas antes de la versión 0.8.0, el botón **Aplicar perfiles sugeridos** crea los perfiles que falten y asigna los sugeridos sin cambiar lo que ya esté configurado.

### Artículos

Los artículos son **compartidos por todas las empresas**. No guardan cuentas: en cada empresa las toman del perfil contable de su categoría.

| Campo | Regla |
| --- | --- |
| Código | Si se deja vacío, el ERP usa el **siguiente correlativo de la categoría** (`SUM-OFI-0001`, `SUM-OFI-0002`…). Se puede escribir uno propio (por ejemplo, al migrar de otro sistema): mayúsculas, números, `.`, `-` o `_`, hasta 30. Único; no cambia |
| Descripción | Obligatoria, hasta 240 caracteres |
| Tipo | Bien inventariable · Bien no inventariable · Servicio · Activo fijo. **Debe coincidir con el tipo del perfil contable de la categoría** en cada empresa que lo tenga |
| Categoría | Obligatoria y activa |
| Unidad de medida | Obligatoria y activa |
| Impuesto | Código del impuesto (por defecto `IGV18`); cada empresa aplica el suyo |
| Marca y modelo | Opcionales; aparecerán en la orden de compra |
| Especificación técnica | Opcional, hasta 4000 caracteres; se enviará al proveedor con la orden de compra |
| Precio referencial | Opcional, con su moneda; las solicitudes lo usarán para estimar el monto |
| Activo | Un artículo inactivo no se puede pedir |

**Configuración contable por empresa.** La ficha muestra, para cada empresa activa, el perfil que usa el artículo, de dónde viene (su categoría o una excepción), la cuenta de cargo, la cuenta por pagar, el impuesto y si **ya se puede comprar**. Si la categoría no tiene perfil en una empresa, el artículo se guarda igual, pero esa empresa no podrá comprarlo hasta que Contabilidad le asigne uno.

**Excepción contable.** Cuando un artículo debe ir a otra cuenta que el resto de su categoría (por ejemplo, un proyector en *Equipos de cómputo* que la empresa registra como mueble), el contador elige otro perfil del mismo tipo para ese artículo y esa empresa (permiso `contabilidad.perfil.editar`).

**Unidades alternativas.** Para pedir en una unidad y recibir en otra: 1 CJA = 12 UND propio de cada artículo. Las conversiones generales (1 DOC = 12 UND, 1 KG = 1000 G) se aplican solas.

**Reglas que protegen la contabilidad:**

- No se guarda un artículo cuyo tipo no coincide con el perfil de su categoría en alguna empresa.
- Contabilidad no puede cambiar el perfil de una categoría si deja artículos de otro tipo en esa rama; debe moverlos de categoría o definirles una excepción.
- El código de impuesto debe existir en alguna empresa.

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

Los proveedores son **compartidos por todas las empresas**: un mismo documento se registra una sola vez. Cada empresa puede **bloquear** a un proveedor para sí, con un motivo; una empresa bloqueada no podrá emitirle órdenes de compra.

| Campo | Regla |
| --- | --- |
| Tipo y número de documento | **RUC** (11 dígitos con dígito verificador), **DNI** (8 dígitos) o **identificación tributaria del exterior** (3 a 20 letras o números, con el país del proveedor). Único; no cambia |
| País | Perú para RUC y DNI; el del proveedor (código de 2 letras) para los del exterior |
| Razón social | Obligatoria |
| Nombre comercial, dirección, correo, teléfono | Opcionales; el correo se valida |
| Moneda habitual | Por defecto PEN para proveedores locales y USD para los del exterior |
| Condición de pago | Por defecto Contado. La orden de compra tomará la moneda y la condición del proveedor |
| Activo | Un proveedor inactivo no recibe órdenes de compra |

**Contactos.** Nombre, cargo, correo y teléfono. Siempre hay un **contacto principal** (el primero que se registra), que recibirá las órdenes de compra; para cambiarlo se marca otro como principal.

**Cuentas bancarias.** Banco, tipo (corriente, ahorros o detracciones), moneda y número.

- Cuentas en Perú: el **CCI de 20 dígitos** es obligatorio. Cuentas del exterior: el **SWIFT/BIC** es obligatorio.
- Por seguridad (el cambio de cuenta bancaria es una vía común de fraude), solo quien tiene `maestros.proveedor.banco` ve los números completos y registra o desactiva cuentas; los demás ven `•••• 1234`.
- Las cuentas no se editan: se desactiva la anterior y se registra la nueva. La auditoría guarda cada cambio sin el número completo.

**Categorías que provee.** Las categorías de artículo que vende el proveedor; servirán para sugerirlo al comprar.

### Condiciones de pago

Vienen precargadas: Contado, Crédito 15, 30, 45 y 60 días. Se pueden crear otras (código, nombre y días de crédito). No se desactiva una condición mientras la use algún proveedor activo.

## 5. Reglas de negocio

- Un artículo no se guarda si su perfil no se resuelve o si el tipo del perfil no coincide con el del artículo.
- Cambiar el perfil de una categoría afecta a las **compras nuevas**; las líneas ya creadas conservan la cuenta que guardaron.
- No se puede eliminar una categoría con artículos ni con subcategorías; solo desactivarla.
- Todo cambio queda en la auditoría.

## 6. Reportes

- Artículos por categoría con su combinación contable (exportable a Excel).

## 7. Configuración por país

La plantilla contable, los impuestos y las unidades de medida precargadas vienen del paquete del país. Perú: [plantilla PCGE](../paises/peru.md).

## 8. Preguntas frecuentes

**¿El usuario de compras tiene que saber de cuentas contables?** No. Elige el artículo; la cuenta sale de la categoría.

**Un proveedor nos falló en una sola empresa del grupo, ¿lo desactivo?** No: bloquéalo solo para esa empresa, con el motivo. Las demás pueden seguir comprándole.

**Tenemos dos empresas: ¿debo crear las categorías dos veces?** No. El árbol es uno solo; el contador de cada empresa asigna su perfil contable.

**Hoy es feriado y no hay tipo de cambio, ¿qué pasa?** El ERP toma el último registrado antes de esa fecha.

**¿Puedo cambiar el RUC de una empresa mal registrada?** No. Desactívala y crea la empresa correcta; así la auditoría conserva la historia.

**¿Qué pasa cuando entre en vigencia el PCGE 2026?** Se agrega la plantilla `PCGE-2026` y el contador reasigna las cuentas de los perfiles; artículos y categorías no cambian.
