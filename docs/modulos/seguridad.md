# Seguridad

**Versión:** 0.11.0 · **Estado:** disponible

## 1. Objetivo del módulo

Controla quién ingresa a Victoria ERP y qué puede hacer cada persona. Permite al administrador crear usuarios, agruparlos en roles, activar solo los módulos que la empresa usa, personalizar el logo y el nombre de la empresa y consultar un registro de todo lo que ocurre.

## 2. Roles y permisos

Existen dos formas de dar acceso:

- **Administrador:** tiene todos los permisos de los módulos activos. Es el único que puede crear otros administradores.
- **Roles:** agrupan permisos de un puesto de trabajo (por ejemplo, Comprador o Aprobador). Un usuario puede tener varios roles; sus permisos se suman.

### Tipos de rol

Todo rol pertenece a uno de estos tipos:

| Tipo | Para qué sirve |
| --- | --- |
| Administrador | Control total del módulo |
| Configuración | Parametriza el módulo sin operar el día a día |
| Operativo | Ejecuta las transacciones diarias |
| Consulta | Solo lectura y auditoría |

### Roles estándar

Cada módulo trae roles estándar listos para usar. Se crean solos al instalar o actualizar el ERP, no se pueden editar ni desactivar, y cada versión los mantiene al día. Para adaptarlos a tu empresa, usa **Duplicar**: la copia conserva el tipo y los permisos, y sí se puede ajustar.

### Nomenclatura de roles

Todo rol, estándar o propio, usa el código `ERP_<MÓDULO>_<FUNCIÓN>` en mayúsculas:

| Módulo | Abreviatura | Ejemplo |
| --- | --- | --- |
| Seguridad | SEG | `ERP_SEG_ADMINISTRADOR` |
| Maestros | MAE | `ERP_MAE_ANALISTA` |
| Solicitudes de compra | SOL | `ERP_SOL_APROBADOR` |
| Compras | COM | `ERP_COM_ANALISTA` |

El código se genera desde el nombre del rol, debe usar la abreviatura del módulo al que pertenece el rol y solo admite letras mayúsculas, números y guion bajo. Si una versión nueva del ERP trae un rol estándar con el mismo código que un rol propio, el rol propio se renombra con el sufijo `_CLIENTE` y queda registrado en la auditoría.

Roles estándar de Seguridad:

| Rol | Tipo | Código | Permisos |
| --- | --- | --- | --- |
| Administrador de seguridad | Administrador | `ERP_SEG_ADMINISTRADOR` | Todos los del módulo |
| Configurador del sistema | Configuración | `ERP_SEG_CONFIGURADOR` | Módulos, roles y personalización |
| Gestor de usuarios | Operativo | `ERP_SEG_GESTOR_USUARIOS` | Usuarios (ver, crear, editar) y ver roles |
| Auditor | Consulta | `ERP_SEG_AUDITOR` | Ver usuarios, roles, módulos y auditoría |

Permisos del módulo:

| Permiso | Permite |
| --- | --- |
| `seguridad.usuario.ver` | Ver la lista de usuarios |
| `seguridad.usuario.crear` | Crear usuarios |
| `seguridad.usuario.editar` | Editar usuarios, cambiar contraseñas y asignar roles |
| `seguridad.rol.ver` | Ver roles y el catálogo de permisos |
| `seguridad.rol.crear` | Crear roles |
| `seguridad.rol.editar` | Editar roles y sus permisos |
| `seguridad.modulo.ver` | Ver los módulos |
| `seguridad.modulo.editar` | Activar y desactivar módulos |
| `seguridad.personalizacion.editar` | Cambiar el logo y el nombre de la empresa |
| `seguridad.auditoria.ver` | Consultar la auditoría |

## 3. Flujo del proceso

1. Al instalar el ERP se crea automáticamente un **administrador inicial** (correo y contraseña definidos en la configuración del ambiente).
2. El administrador **activa los módulos** que la empresa va a usar.
3. El administrador **asigna roles estándar** o, si necesita variantes, los **duplica** y ajusta sus permisos.
4. El administrador **crea los usuarios** y les asigna uno o más roles.
5. Cada usuario **ingresa** con su correo y contraseña y solo ve en el menú las pantallas que sus permisos permiten.

### Organización del menú

- **Arriba:** los módulos de negocio (Solicitudes, Compras, Inventarios…). Es lo que el usuario usa a diario.
- **Al pie, plegado:** el grupo **⚙ Administración**, con Usuarios, Roles, Módulos, Personalización y Auditoría. Se abre con un clic, recuerda si lo dejaste abierto y se abre solo cuando entras a una de sus pantallas.
- Un usuario sin permisos de administración no ve el grupo.

### Confirmación de cada acción

- Mientras se guarda, el botón muestra un indicador giratorio y el texto *Guardando…*.
- Al terminar, aparece una notificación abajo a la derecha (por ejemplo *Usuario creado*) y, en formularios que no se cierran, el botón muestra *✓ Guardado* por unos segundos y vuelve a su estado normal.
- Un botón gris significa que la acción **no está permitida**, nunca que algo sigue procesando.
6. Toda acción queda registrada en la **auditoría**.

## 4. Pantallas y campos

### Ingreso

| Campo | Regla |
| --- | --- |
| Correo | Obligatorio; no distingue mayúsculas |
| Contraseña | Obligatoria |

### Usuarios

| Campo | Regla |
| --- | --- |
| Correo | Obligatorio, único; no se puede cambiar después de crearlo |
| Nombre completo | Obligatorio, de 2 a 150 caracteres |
| Contraseña | Mínimo 8 caracteres; al editar, si se deja vacía no cambia |
| Roles | Opcional; uno o varios |
| Administrador | Solo visible para administradores |
| Usuario activo | Un usuario inactivo no puede ingresar |

### Roles

| Campo | Regla |
| --- | --- |
| Nombre | Obligatorio, de 2 a 100 caracteres |
| Módulo | Obligatorio; define la abreviatura del código |
| Código | `ERP_<MÓDULO>_<FUNCIÓN>`; se genera desde el nombre; único; no se puede cambiar |
| Tipo | Obligatorio: administrador, configuración, operativo o consulta |
| Descripción | Opcional, hasta 300 caracteres |
| Permisos | Agrupados por módulo, con opción de marcar todos |
| Rol activo | Si se desactiva, sus usuarios pierden esos permisos de inmediato |

### Módulos

Lista de módulos con un interruptor para activarlos o desactivarlos. Seguridad está siempre activo.

### Personalización

| Campo | Regla |
| --- | --- |
| Logo | PNG, JPG o WebP de hasta 2 MB; el formato se verifica por el contenido del archivo. No se acepta SVG porque puede contener código. Se recomienda al menos 600 px de ancho: si la imagen es más pequeña se acepta, pero la pantalla avisa que podría verse borrosa |
| Nombre de la empresa | Opcional, hasta 150 caracteres |

El logo y el nombre aparecen en la pantalla de ingreso (antes de iniciar sesión) y en el menú lateral.

!!! tip "Para un logo nítido"
    Usa un PNG horizontal con fondo transparente de 600 a 1200 px de ancho. En el menú el logo se muestra en unos 200 px; una imagen más grande se ve nítida también en pantallas de alta resolución.

### Acceso por empresa y unidad de negocio

En la ficha de cada usuario (*Administración → Usuarios*) se marcan las **empresas** a las que tiene acceso y, en cada una, **todas sus unidades de negocio** (incluidas las que se creen después) o solo algunas.

- Un usuario **sin empresas asignadas no ve ninguna**: la lista de usuarios lo marca con *Sin empresas*.
- El **administrador** ve todas las empresas, sin asignación.
- Quien crea una empresa obtiene acceso a ella automáticamente.
- El acceso se verifica en el servidor en toda pantalla y operación que trabaja sobre una empresa (plan de cuentas, perfiles, centros de costo, impuestos, empresas, bloqueo de proveedores) y en la configuración contable que se muestra en la ficha de un artículo. Las solicitudes y órdenes de compra también exigirán acceso a la unidad de negocio.
- Asignar accesos requiere `seguridad.usuario.editar` y queda en la auditoría con lo anterior y lo nuevo.

### Atributos adicionales

*Administración → Atributos adicionales* ([ADR-005](../adr/0005-atributos-adicionales.md)). Para cada documento operativo (solicitud de compra, orden de compra) y cada nivel (cabecera, línea, distribución) hay 10 atributos de texto, 10 numéricos y 10 de fecha, todos inactivos al inicio. La configuración es una sola para todo el grupo de empresas.

| Campo | Regla |
| --- | --- |
| Nombre | Obligatorio para activar; no se repite entre los atributos activos del mismo documento y nivel |
| Texto de ayuda | Opcional; se muestra debajo del campo |
| Lista de valores | Solo atributos de texto, uno por línea, sin repetidos; el usuario elige de la lista |
| Valor por defecto | Opcional; del tipo del atributo y, si hay lista, uno de sus valores |
| Copiar al documento siguiente | Atributo activo del documento siguiente, del mismo tipo y nivel. Dos atributos no pueden copiarse al mismo destino. No se desactiva un atributo que recibe una copia |

La pantalla muestra una **vista previa** de los campos tal como los verá el usuario. Permiso: `seguridad.atributo.editar` (rol Configurador del sistema). Todo cambio queda en la auditoría.

### Auditoría

Lista de eventos con fecha, usuario, acción y detalle de los cambios (valor anterior → valor nuevo). Se puede filtrar por usuarios, roles, módulos o ingresos.

## 5. Reglas de negocio y validaciones

- El correo de un usuario es único, sin importar mayúsculas.
- Solo un administrador puede crear administradores o cambiar ese atributo.
- Nadie puede desactivarse ni quitarse la administración a sí mismo (evita quedarse sin acceso).
- El módulo Seguridad no se puede desactivar.
- Si un módulo está inactivo, sus permisos no aplican aunque el rol los tenga.
- Un rol solo puede tener permisos que existen en el catálogo.
- Todo rol tiene un tipo.
- Los roles estándar no se pueden editar ni desactivar; si alguien los altera en la base, el ERP los restaura al reiniciar.
- La sesión vence a las 8 horas (configurable).
- Los intentos de ingreso fallidos quedan registrados.
- La auditoría no se puede editar ni borrar.

## 6. Reportes disponibles

| Reporte | Dónde |
| --- | --- |
| Usuarios con roles, estado y último acceso | Pantalla Usuarios |
| Roles con número de permisos | Pantalla Roles |
| Bitácora de cambios e ingresos | Pantalla Auditoría |

La exportación a Excel se agregará en la semana 5 junto con el reporte de compras.

## 7. Configuración por país

Este módulo no tiene reglas propias por país.

## 8. Preguntas frecuentes

**Olvidé la contraseña del administrador.**
Otro administrador puede asignarte una nueva desde Usuarios. Si no hay otro, el equipo técnico la restablece en el ambiente.

**Un usuario no ve una pantalla que necesita.**
Revisa que tenga un rol activo con el permiso `*.ver` de esa pantalla y que el módulo esté activo.

**¿Por qué no puedo desactivar el módulo Seguridad?**
Porque sin él nadie podría ingresar ni administrar el ERP.

## Referencia técnica

| Método | Ruta | Permiso |
| --- | --- | --- |
| POST | `/api/v1/seguridad/auth/login` | Público |
| GET | `/api/v1/seguridad/auth/sesion` | Usuario autenticado |
| GET | `/api/v1/seguridad/usuarios` | `seguridad.usuario.ver` |
| POST | `/api/v1/seguridad/usuarios` | `seguridad.usuario.crear` |
| GET | `/api/v1/seguridad/usuarios/{id}` | `seguridad.usuario.ver` |
| PATCH | `/api/v1/seguridad/usuarios/{id}` | `seguridad.usuario.editar` |
| GET | `/api/v1/seguridad/roles` | `seguridad.rol.ver` |
| POST | `/api/v1/seguridad/roles` | `seguridad.rol.crear` |
| PATCH | `/api/v1/seguridad/roles/{id}` | `seguridad.rol.editar` |
| POST | `/api/v1/seguridad/roles/{id}/duplicar` | `seguridad.rol.crear` |
| GET | `/api/v1/seguridad/tipos-rol` | `seguridad.rol.ver` |
| GET | `/api/v1/seguridad/permisos` | `seguridad.rol.ver` |
| GET | `/api/v1/seguridad/modulos` | `seguridad.modulo.ver` |
| PATCH | `/api/v1/seguridad/modulos/{codigo}` | `seguridad.modulo.editar` |
| GET | `/api/v1/seguridad/personalizacion` | Público |
| GET | `/api/v1/seguridad/personalizacion/logo` | Público |
| PUT | `/api/v1/seguridad/personalizacion` | `seguridad.personalizacion.editar` |
| PUT | `/api/v1/seguridad/personalizacion/logo` | `seguridad.personalizacion.editar` |
| DELETE | `/api/v1/seguridad/personalizacion/logo` | `seguridad.personalizacion.editar` |
| GET | `/api/v1/seguridad/auditoria` | `seguridad.auditoria.ver` |

Tablas: `seg_usuario`, `seg_rol`, `seg_permiso`, `seg_modulo`, `seg_usuario_rol`, `seg_rol_permiso`, `seg_auditoria`, `seg_personalizacion`.

Para que un módulo nuevo traiga sus roles estándar, agrégalos en `catalogo.ROLES_ESTANDAR` con un rol por tipo que aplique.

Para proteger una ruta de otro módulo:

```python
from app.modules.seguridad.deps import requiere

@router.post("/ordenes")
def crear_orden(actor = Depends(requiere("compras.orden.crear"))):
    ...
```
