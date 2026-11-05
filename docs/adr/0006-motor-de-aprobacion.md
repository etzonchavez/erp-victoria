# ADR-006: Motor de aprobación configurable

**Estado:** aprobado · 31 oct 2026

## Contexto

Las solicitudes de compra (y luego las órdenes, facturas y pagos) necesitan aprobación. Cada cliente aprueba distinto: por monto, por área, por tipo de compra, con varias firmas en orden o en paralelo. Si las reglas viven en el código, cada cliente nuevo pide un desarrollo.

## Decisión

Un **motor de aprobación común** (`app/modules/aprobaciones`, tablas `apr_`), configurable por el cliente, que usan todos los documentos que se aprueban.

**Regla de aprobación** (por empresa y documento):

- **Condiciones opcionales:** unidad de negocio, categoría de artículo (incluye sus subcategorías), tipo de artículo y centro de costo. Un documento cumple una condición si al menos una de sus líneas la cumple.
- **Prioridad:** se usa la primera regla activa, de menor número, cuyas condiciones se cumplen todas. Dos reglas no comparten prioridad.
- Sin regla aplicable, **el documento no se envía** (decisión de Et): el ERP pide avisar al administrador.

**Niveles** (hasta 3 por regla), en orden: el nivel 2 empieza cuando termina el 1.

- **Monto desde:** el nivel se activa si el total, en la moneda de la empresa, lo alcanza. Los montos no pueden bajar de un nivel al siguiente.
- **Modo:** *en serie* (uno tras otro), *paralelo · todos* (todos deben aprobar) o *paralelo · basta uno* (el primero que aprueba cierra el nivel).
- Si ningún nivel alcanza el monto, el documento se aprueba al enviarlo.

**Aprobadores** de cada nivel, cada uno con condiciones opcionales propias (unidad, categoría, centro de costo):

| Tipo | Quién aprueba |
| --- | --- |
| Usuario específico | Esa persona |
| Rol | Cualquier usuario con ese rol y acceso a la unidad de negocio del documento |
| Responsable del centro de costo | El usuario responsable de cada centro de costo del documento (uno por centro) |
| Jefe del solicitante | El jefe inmediato registrado en la ficha del usuario |

**Reglas fijas:**

1. El solicitante nunca aprueba lo suyo: su paso se marca *omitido* y sigue el siguiente.
2. Un mismo usuario aparece una sola vez por nivel.
3. Rechazar termina el flujo; devolver regresa el documento al solicitante y, al reenviarlo, empieza una **ronda** nueva desde el nivel 1.
4. Rechazar y devolver exigen comentario. Todo queda en la auditoría.
5. Si al enviar falta un dato para resolver un aprobador (jefe no registrado, centro sin responsable, rol sin usuarios), el envío se bloquea con un mensaje que dice qué falta.

**Ejecución:** al enviar, el motor "congela" los aprobadores en pasos (`apr_paso`) con su descripción. Cambiar la regla después no altera los documentos ya enviados.

## Cómo lo usa un documento

```python
from app.modules.aprobaciones import service as aprobaciones

ctx = aprobaciones.Contexto(documento="orden_compra", documento_id=oc.id, empresa_id=...,
                            unidad_negocio_id=..., solicitante_id=..., monto=total_funcional,
                            categorias=..., tipos=..., centros=[...])
aprobaciones.simular(db, ctx)                      # vista previa
estado = aprobaciones.iniciar(db, ctx, ronda)      # "en_aprobacion" | "aprobado"
estado = aprobaciones.actuar(db, actor, ctx, ronda, "aprobar", comentario)
```

## Consecuencias

- Las órdenes de compra ya lo usan (documento `orden_compra`, 0.15.0) con reglas propias; los documentos futuros se aprueban sin construir otro flujo.
- Las reglas se administran en `/api/v1/aprobaciones` con el permiso del documento (`solicitudes.regla.*`, `compras.regla.*`).
- No hay delegación ni reemplazo por vacaciones todavía: se agregará como "aprobador suplente" con vigencia.
- No hay escalamiento por tiempo (SLA): queda para cuando existan notificaciones por correo.
