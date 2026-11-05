# ADR-007: PDF de la orden de compra con formato configurable

**Estado:** aprobado · 4 nov 2026

## Contexto

La orden de compra es el documento que recibe el proveedor. Cada cliente quiere su logo, sus colores, sus términos y decidir qué datos imprimir y en qué orden (decisión de Et: "PDF configurable, con el logo y distribución de los datos de la OC"). Debe hacerse sin programar por cliente y sin costo de licencias (ADR-003).

## Decisión

1. **Un formato por empresa** (`cmp_formato`), editado en *Compras → Formato de la orden* con vista previa en vivo.
2. El formato se guarda como configuración JSON validada en el servidor:

| Opción | Valores |
| --- | --- |
| Título | Texto (por defecto ORDEN DE COMPRA) |
| Color | Hexadecimal; colorea encabezado, títulos y tabla |
| Tamaño | A4 o carta |
| Datos por fila | 1, 2 o 3 bloques lado a lado (proveedor, entrega, condiciones, datos adicionales) |
| Logo | Propio del formato (PNG, JPG o WebP, hasta 2 MB) o, si no hay, el logo general del ERP; se puede ocultar |
| Secciones | Proveedor, entrega, condiciones, detalle, totales, datos adicionales (atributos de cabecera activos), observaciones, términos, aprobaciones (firmas). Cada una se activa y se ordena |
| Columnas del detalle | N.°, código, descripción (siempre), cantidad, unidad, precio, impuesto, subtotal, total, centro de costo, solicitud de origen |
| Términos y pie | Texto libre; el pie va en todas las páginas junto a "Página X de Y" |

3. El PDF se arma como **HTML + CSS** y lo convierte **WeasyPrint** (libre, BSD). Ventajas: el diseño se cambia con CSS, soporta saltos de página, encabezados y pies por página, y el mismo motor servirá para otros documentos (recepción, liquidaciones).
4. Una orden que no está **Aprobada** ni **Enviada** se imprime con marca de agua de su estado (BORRADOR, EN APROBACIÓN…), para que nunca circule como válida.
5. Las firmas salen del historial de aprobación de la ronda vigente (quién aprobó, en qué nivel y cuándo) más quién emitió.

## Consecuencias

- El servidor necesita las librerías de sistema de WeasyPrint (Pango, HarfBuzz y una fuente): están en el `Dockerfile` y en la integración continua.
- Hoy hay un solo formato por empresa (decisión de Et). Si se piden formatos distintos para bienes y servicios, la tabla admite agregar una clave de formato sin romper lo existente.
- La plantilla HTML vive en `app/modules/compras/pdf.py`; un diseño totalmente libre por cliente (editor visual) queda fuera del alcance.
