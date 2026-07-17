# Arquitectura de Dashboard Gerencial sobre Effi Systems — Guía de Referencia

> Documento genérico de arquitectura y patrones técnicos para construir un dashboard gerencial que consume datos del ERP **Effi Systems** vía scraping (Effi no expone API pública). No contiene información de ninguna empresa específica — es el esqueleto a partir del cual se arranca un proyecto nuevo.

---

## 1. Filosofía del proyecto

Un solo patrón se repite en cada módulo:

```
Effi (ERP web, sin API pública)
  ↓ Playwright navega y descarga Excel (exportación HTML con extensión .xls)
Excel crudo (reportes/raw/*)
  ↓ pandas limpia, corrige encoding/decimales y agrega
JSON intermedio (reportes/*.json)
  ↓ Python genera HTML con f-strings (sin framework frontend, sin build step)
dashboard.html (un solo archivo estático)
  ↓ git commit + push
GitHub Pages (público, gratis, sin backend, sin servidor que mantener)
```

**Por qué este patrón y no un stack tradicional (React/Vue + API + base de datos):**
- Cero backend que mantener, cero servidor que se caiga, cero costo de hosting.
- Un solo archivo HTML es fácil de depurar (Ctrl+F en el navegador) y fácil de compartir (un link).
- Effi no tiene API pública — Playwright simula al usuario navegando y exportando Excel, que es lo único disponible.
- Los JSON intermedios permiten reprocesar/regenerar el HTML sin volver a scrapear (separación descarga vs. procesamiento vs. presentación).

---

## 2. Cómo se descargan datos de Effi (mecánica general)

### 2.1 Autenticación y sesión

- URL de login: `https://effi.com.co/ingreso`
- URL base de la app: `https://effi.com.co/app/`
- Effi usa cookies de sesión estándar. El patrón que funciona:
  1. Login con Playwright (`page.goto` a `/ingreso`, llenar usuario/contraseña, submit, esperar a que la URL deje de contener `ingreso`/`login`).
  2. Guardar el `storage_state` del contexto de Playwright (cookies) en un archivo local (ej. `~/.{proyecto}_session.json`).
  3. En corridas posteriores, crear el contexto de Playwright con `storage_state=<ese archivo>` en vez de loguear de nuevo — evita golpear el login (y un eventual reCAPTCHA) en cada ejecución.
  4. Antes de usar la sesión guardada, verificar que siga viva navegando a cualquier URL interna y comprobando que no redirigió a `/ingreso`.
  5. Si la sesión expiró, reintentar login automático con credenciales guardadas (cifradas localmente, nunca en texto plano en el repo); si eso también falla (típicamente por reCAPTCHA), abortar sin publicar y avisar — nunca forzar el captcha automáticamente.

### 2.2 Descarga de reportes (exportación a Excel)

Effi exporta desde casi cualquier listado vía un flujo de "Reportes y análisis de datos" → "Reporte de conceptos" → selección de columnas → botón Exportar. Patrón Playwright reutilizable:

```python
def navegar_y_descargar(page, desde, hasta, sufijo, url_base, columnas):
    url = f"{url_base}?desde={desde}%2000:00:00&hasta={hasta}%2023:59:59"
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(5)  # Effi es una SPA lenta; esperas fijas son más confiables que esperar selectores específicos
    page.locator("a:has-text('Reportes y análisis de datos')").click()
    page.locator("a:has-text('Reporte de conceptos')").click()
    page.locator("text=Seleccione las columnas").wait_for(state="visible")
    for col in columnas:
        chk = page.locator(f"label:has-text('{col}') input[type='checkbox']")
        if chk.count() and not chk.first.is_checked():
            chk.first.check()
    with page.expect_download(timeout=240_000) as dl_info:
        page.locator("button:has-text('Exportar'), input[value*='Exportar' i]").first.click()
    ruta = RAW_DIR / f"raw_{sufijo}.xlsx"
    dl_info.value.save_as(str(ruta))
    return ruta
```

**Filtrado por fecha**: casi todos los módulos de Effi aceptan un rango `desde`/`hasta` inyectado en el formulario (a veces vía querystring, a veces inyectando JS directo sobre los `<input>` del datepicker si el querystring no responde — probar ambos). **Siempre confirmar en la UI de Effi cuál campo de fecha corresponde al filtro** antes de asumirlo (ver sección 2.4 — es la trampa más costosa del proyecto).

### 2.3 Leer el Excel exportado (dos trampas críticas)

Los archivos que exporta Effi **no son binarios Excel reales** — son HTML con extensión `.xls`/`.xlsx`. Hay que leerlos así:

```python
df = pd.read_html(str(ruta), encoding="ISO-8859-1", decimal=",", thousands=".")[0]
```

- `encoding="ISO-8859-1"` — sin esto, las tildes/ñ salen corruptas.
- **`decimal=","` es la trampa más cara de todo el proyecto.** Effi exporta números en formato colombiano (`3.000.000,00` = tres millones). Sin `decimal=","`, pandas interpreta el punto como separador decimal y el número queda **100 veces inflado** (`3.000.000,00` se lee como `3,000,000.00` × 100 en vez de `3,000,000.00` reales — ej. un saldo de $524,770,823 se leía como $52,477,082,398). Verificar SIEMPRE un total contra lo que muestra la UI de Effi antes de confiar en un módulo nuevo.

### 2.4 Filtrar por la fecha correcta (segunda trampa cara)

Cada documento en Effi tiene **múltiples fechas** (fecha de creación del registro, fecha del movimiento/ingreso/egreso, fecha de vencimiento, etc.) y casi nunca son la misma. Regla general:
- Para reportes de caja/tesorería (ingresos, egresos), filtrar por la **fecha del movimiento real** (ej. "Fecha del ingreso"/"Fecha del egreso"), nunca por "Fecha de creación" del comprobante — alguien puede registrar hoy un pago que ocurrió hace una semana.
- Para ventas (remisiones/facturas), suele ser al revés: la fecha de creación del documento SÍ es la referencia contable oficial, salvo que el negocio decida explícitamente usar fecha de entrega u otra.
- **Nunca asumir — preguntar al usuario del negocio cuál es la fecha correcta para cada módulo**, y dejarlo documentado en el código con un comentario explicando por qué.

### 2.5 Detección de columnas por nombre aproximado

Effi no siempre exporta el mismo nombre de columna entre módulos o entre pequeñas actualizaciones de la plataforma. Usar un alias/búsqueda flexible en vez de nombres exactos:

```python
col_total = next((c for c in df.columns if 'precio neto total' in c.lower()), None)
col_tercero = next((c for c in df.columns if c.lower() in ('tercero', 'nombre tercero')), None)
```

### 2.6 Módulos típicos de Effi que un dashboard gerencial suele necesitar

| Módulo Effi | URL típica | Para qué sirve |
|---|---|---|
| Remisiones | `/app/remision_v` | Ventas (documento previo a factura) |
| Facturas | `/app/factura_v` | Ventas facturadas |
| Artículos / Inventario | `/app/articulo` | Catálogo, existencias por bodega |
| Terceros → Clientes | `/app/tercero/cliente` | Base de clientes |
| Terceros → Proveedores | `/app/tercero/proveedor` | Base de proveedores |
| Terceros → Empleados | `/app/tercero/empleado` | Base de empleados (cruzar contra comprobantes de egreso para detectar nómina real) |
| Cuentas por Pagar | `/app/c_x_p/consultar` | Obligaciones pendientes |
| Cuentas por Cobrar | `/app/c_x_c/consultar` | Cartera de clientes |
| Comprobantes de Ingreso | `/app/ingreso` | Movimientos de caja entrantes |
| Comprobantes de Egreso | `/app/egreso` | Movimientos de caja salientes / gastos |
| Transferencias internas | `/app/transferencia_interna_dinero` | Movimientos entre cuentas propias (excluir de "gasto real") |

No todas las empresas usan todos los módulos — empezar por Remisiones/Facturas + Comprobantes de Ingreso/Egreso, que son universales, y agregar el resto según lo que el negocio realmente use.

---

## 3. Los 3 scripts raíz (patrón de orquestación)

| Script | Cuándo corre | Qué hace |
|---|---|---|
| `reporte_completo.py` | Manual, 1 vez por semana/mes | Login completo a Effi (usuario+clave), descarga TODO, genera el HTML completo, publica. |
| `actualizar_dashboard.py` | Automático, cada hora (cron/LaunchAgent) | Reutiliza la sesión ya guardada (cookies), descarga solo el período en curso, regenera y publica. Si la sesión expiró, intenta auto-login con credenciales guardadas; si falla (captcha), se detiene sin publicar. |
| `verificar_sesion.py` | Al encender la máquina / montar volumen | Verifica si la sesión de Effi sigue viva; si no, abre un navegador visible para reloguear manualmente y guarda la sesión nueva. |

**Regla de oro:** *solo estos scripts pueden llamar a la función que publica en GitHub Pages*. Cualquier script de prueba/debug debe detenerse antes del paso de publicación, para que un experimento no le "pise" el dashboard real a los usuarios.

---

## 4. Motor de generación de HTML

Un único archivo con una función grande `generar_dashboard_html(df, ...)` que construye TODO el HTML como un string de Python usando f-strings — sin Jinja, sin React, sin build step. Ventaja: cero dependencias de build, un solo artefacto para desplegar. Desventaja: el archivo crece mucho — es un trade-off consciente a cambio de simplicidad de despliegue (funciona bien hasta varios miles de líneas).

### 4.1 Trampa de f-strings con comillas dentro de JS embebido

Dentro de f-strings con comillas triples, `\'` se convierte en `'` **sin backslash**, lo que rompe JavaScript embebido:

```python
# INCORRECTO — genera SyntaxError JS al ejecutarse en el navegador:
s += f'<div onclick="fn(\'{var}\')">'

# CORRECTO — usar atributos data-* en vez de interpolar dentro de un string JS:
s += f'<div onclick="fn(this.dataset.id)" data-id="{var}">'
```

### 4.2 Llaves literales en f-strings

`{{` y `}}` en un f-string producen `{` y `}` literales en el output — indispensable para CSS y JS embebidos, pero fácil de desbalancear. **Siempre validar sintaxis antes de regenerar:**

```bash
python3 -c "import ast; ast.parse(open('generar_dashboard.py').read()); print('OK')"
```

Y para el JS embebido, extraerlo y validarlo con Node antes de publicar:

```bash
python3 -c "
import re
html = open('dashboard.html').read()
scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.S)
open('/tmp/check.js','w').write(scripts[N])
"
node --check /tmp/check.js
```

### 4.3 Orden del DOM vs. orden de ejecución de `<script>`

Un `<script>` que corre `document.getElementById('X').innerHTML` **falla silenciosamente con un error que aborta todo el bloque de JS** si el elemento `X` todavía no ha sido parseado por el navegador (porque vive más abajo en el HTML). Esto puede romper botones que ni siquiera tocan ese elemento, con un debug muy confuso. Patrón seguro — capturar contenido original de forma diferida, no al momento de definir el script:

```javascript
function _cachearOriginales(){
  if(!window._origX){ var el=document.getElementById('X'); if(el) window._origX = el.innerHTML; }
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _cachearOriginales);
else _cachearOriginales();
```

### 4.4 Secciones "lazy-loaded"

Si el HTML principal crece demasiado, las secciones pesadas (tablas de miles de filas) se escriben a un archivo aparte (`sec_X.html`) y en el HTML principal solo queda un placeholder que se inyecta por `fetch()` cuando el usuario hace clic en esa pestaña:

```python
_html_seccion = construir_seccion_pesada()
(Path('reportes') / 'sec_X.html').write_text(_html_seccion, encoding='utf-8')
_html_seccion = '<div id="X-lazy-wrap">⏳ Cargando...</div>'  # lo que sí va en el HTML principal
```

```javascript
if(sec==="X" && !window._xCargado){
  window._xCargado = true;
  fetch("https://usuario.github.io/repo/sec_X.html").then(r=>r.text()).then(html=>{
    document.getElementById('X-lazy-wrap').outerHTML = html;
  });
}
```

Estos archivos `sec_*.html` deben agregarse a la lista de archivos que publican tanto el script semanal como el horario.

---

## 5. Módulos de dashboard genéricos (aplican a cualquier empresa con Effi)

### 5.1 Mesa de Gerencia (KPIs financieros del período)
Ingresos, egresos, cartera CxP/CxC, nómina, margen — agregados desde comprobantes/remisiones procesadas a un JSON intermedio (ej. `financiero_procesado.json`).

### 5.2 Ventas por Punto de Venta / Composición de Venta
Barras por sucursal + donut facturado-vs-pendiente. Se agrega por sucursal + marca/línea + estado del documento.

### 5.3 Financiero directo desde Effi

La lección más importante y más cara de todo este tipo de proyecto:

- **El ingreso real se mide por remisiones/facturas con estado de cobro "Pago total"**, NO sumando Comprobantes de Ingreso a ciegas — esos incluyen correcciones de banco, movimientos de caja menor y otros ítems internos que no son ingreso nuevo (sumarlos puede inflar el ingreso 3-4 veces). Validar esto explícitamente con el área financiera del negocio antes de confiar en cualquier cifra.
- Para egresos, sí se puede usar Comprobantes de Egreso, pero:
  - Filtrar por **fecha del egreso real**, nunca por fecha de creación del comprobante.
  - Excluir movimientos de traslado de efectivo entre cuentas propias (no son gasto real).
  - Clasificar por rubro cruzando el campo estructurado si Effi lo exporta + un clasificador por palabras clave sobre el texto libre del concepto (Effi no siempre exporta un tipo de gasto estructurado).
  - Cruzar el **tercero del comprobante contra la base de Empleados** de Effi para detectar nómina real, en vez de adivinar por palabras clave en el texto — mucho más confiable.

### 5.4 Inventario / Rotación
SKU × bodega × familia de producto, con un índice de cobertura (días de stock disponible / demanda proyectada). Requiere un archivo de mapeo manual "categoría Effi → familia de negocio" — las categorías de Effi casi nunca corresponden 1:1 a como el negocio agrupa sus productos, y **siempre** van a aparecer categorías basura (genéricos, gastos, administrativo) que hay que excluir explícitamente de cualquier total de inventario real.

### 5.5 Comercial / Comisiones
Ventas por vendedor/asesor vs. meta, con escalafón de comisión por tramos de cumplimiento. Las metas casi siempre viven en un JSON de configuración manual — no se calculan solas, alguien las actualiza cada período, y el dashboard debe leerlas de ahí, no hardcodearlas en el código de generación de HTML.

---

## 6. Patrones de UI reutilizables

- **Filtro por mes**: todos los meses se pre-renderizan en `<div data-mes="N" style="display:none">` y un `<select>` los muestra/oculta con `querySelectorAll('[data-mes]')`. Barato de generar, cero llamadas a servidor.
- **Filtro por rango de fechas** (más flexible, tipo Shopify): requiere un dataset agregado por DÍA (no por mes) embebido en un objeto global de datos del dashboard — se recalculan las gráficas en JS puro filtrando por fecha, sin volver a tocar Python. Mantener el JSON liviano agregando por día+dimensión (nunca fila por fila).
- **Drawers de detalle**: overlay + panel lateral que se llena dinámicamente al hacer clic en una tarjeta/torta/barra — reutilizar el mismo par de elementos (`#overlay`, `#drawer`) para todos los detalles de un módulo en vez de crear un drawer por cada cosa clickeable.
- **Presupuesto vs. Real editable**: inputs numéricos que guardan en `localStorage` del navegador (no hay backend para persistir cambios) — el usuario ajusta metas directamente en el dashboard sin tocar código ni JSON.
- **Consolidar categorías con sufijo**: cuando el ERP separa una misma familia en variantes (ej. "PRODUCTO" / "PRODUCTO PR"), agrupar quitando el sufijo y ofrecer clic-para-desglosar en vez de mostrar cada variante como fila separada.

---

## 7. Checklist para arrancar un proyecto nuevo con esta arquitectura

1. **Credenciales y sesión**: crear `~/.{proyecto}_session.json` (cookies) y `~/.{proyecto}_effi_credentials` (cifrado local) con nombres propios del proyecto nuevo — nunca compartir archivos de sesión entre proyectos distintos.
2. **Mapear los módulos de Effi que la empresa realmente usa** (no todas usan Cuentas por Pagar/Cobrar, Trazabilidad de Dinero, etc.) — empezar solo por remisiones/facturas + comprobantes de ingreso/egreso.
3. **Construir el mapeo categoría→familia de negocio** específico del catálogo de productos de la empresa (nunca es genérico, cada empresa clasifica distinto).
4. **Definir el escalafón de comisiones** y la estructura de metas por sucursal/vendedor si aplica al negocio.
5. **Definir junto al área financiera qué estados de Effi cuentan como "venta real"** antes de construir cualquier cifra de ingresos — este es el punto que más iteración suele tomar y es distinto en cada empresa según cómo factura.
6. **Crear un repo de GitHub Pages dedicado** para el proyecto (nunca reusar el mismo repo entre empresas distintas).
7. **Empezar solo con Mesa de Gerencia + Ventas por Punto de Venta**, validar que los números cuadren con lo que el gerente ya sabe de memoria, y solo después construir módulos más específicos (inventario, comisiones, financiero detallado).

---

*Documento de arquitectura genérica — sin datos ni lógica de negocio de ninguna empresa específica. Sirve como memoria inicial para levantar un proyecto nuevo sobre Effi Systems.*
