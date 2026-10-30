# Maestros

**Versión:** diseño · **Estado:** en construcción (Semana 3)

## 1. Objetivo del módulo

Registra los datos base que usan todos los procesos: empresa, unidades de negocio, monedas, unidades de medida, proveedores, categorías y artículos. Las categorías y artículos quedan **alineados con la contabilidad base** ([ADR-004](../adr/0004-base-contable.md)), así cada compra sabe a qué cuenta va sin que el usuario elija cuentas.

## 2. Roles y permisos

| Rol estándar | Tipo | Para quién |
| --- | --- | --- |
| `ERP_MAE_ADMINISTRADOR` | administrador | Responsable de datos maestros |
| `ERP_MAE_ANALISTA` | operativo | Crea y edita proveedores y artículos |
| `ERP_MAE_CONSULTA` | consulta | Solo consulta |

| Permiso | Permite |
| --- | --- |
| `maestros.empresa.ver` / `.editar` | Datos de la empresa y unidades de negocio |
| `maestros.moneda.ver` / `.editar` | Monedas y unidades de medida |
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

### Proveedores, empresa, unidades de negocio, monedas, unidades de medida

Se detallan al construirlos (Semana 3, tareas 1 y 4).

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

**¿Qué pasa cuando entre en vigencia el PCGE 2026?** Se agrega la plantilla `PCGE-2026` y el contador reasigna las cuentas de los perfiles; artículos y categorías no cambian.
