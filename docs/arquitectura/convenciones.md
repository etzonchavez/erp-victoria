# Convenciones

## Código

| Elemento | Convención | Ejemplo |
| --- | --- | --- |
| Idioma del código | Nombres de negocio en español, términos técnicos en inglés | `class SolicitudCompra`, `service.py` |
| Python | snake_case para funciones y variables, PascalCase para clases | `aprobar_solicitud()` |
| TypeScript | camelCase para variables, PascalCase para componentes | `SolicitudForm` |
| Formato | Ruff (Python), Prettier (TypeScript) | |

## Base de datos

| Elemento | Convención | Ejemplo |
| --- | --- | --- |
| Tablas | snake_case, prefijo del módulo | `cmp_orden_compra` |
| Llave primaria | `id` UUID | |
| Auditoría | `creado_por`, `creado_en`, `actualizado_por`, `actualizado_en` en toda tabla | |
| Montos | `NUMERIC(18,4)` + código de moneda ISO 4217 | `monto`, `moneda = 'PEN'` |
| Fechas y horas | UTC en BD, zona horaria del usuario en pantalla | |

Prefijos de tablas: `seg` seguridad, `mae` maestros, `sol` solicitudes, `cmp` compras, `inv` inventarios, `cxp` cuentas por pagar, `cnt` contabilidad, `cxc` cuentas por cobrar.

## API

- Ruta base versionada: `/api/v1/<modulo>/<recurso>`.
- Recursos en plural y en minúsculas: `/api/v1/compras/ordenes`.
- Errores con formato único: `{"codigo": "...", "mensaje": "..."}`.
- Toda ruta declara el permiso que exige.

## Git

- Rama principal `main`; trabajo en ramas `semana-N/tarea`.
- Mensajes de commit: `modulo: qué cambió` (ej. `seguridad: alta de roles`).

## Roles

- Todo módulo define en `catalogo.py` un rol estándar por tipo que aplique: administrador, configuración, operativo y consulta.
- Código de todo rol: `ERP_<ABREVIATURA>_<FUNCIÓN>` en mayúsculas (ej. `ERP_COM_ADMINISTRADOR`, `ERP_COM_ANALISTA`). La abreviatura de 3 letras se define en `catalogo.MODULOS`.
- Nombre del rol en español, en singular y por puesto de trabajo.
- Los roles propios del cliente siguen la misma nomenclatura y normalmente se crean duplicando uno estándar.
- Permisos de un rol de consulta: solo acciones `ver`.
