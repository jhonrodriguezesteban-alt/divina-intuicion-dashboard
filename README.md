# Dashboard Gerencial — Divina Intuición

Dashboard de control y gestión para la marca **Divina Intuición** (tiendas de ropa,
3 sucursales: Local 144, Local 107, Local 433), construido sobre la arquitectura
genérica documentada en [`JR ARQUITECTURA_REPLICABLE.md`](./JR%20ARQUITECTURA_REPLICABLE.md).

## Estado del proyecto

Fase 0 — andamiaje inicial. Aún sin acceso confirmado a Effi ni datos reales.

**Alcance de la v1** (los 3 en paralelo, con foco inicial en Mesa de Gerencia + Ventas para validar cifras):
1. Mesa de Gerencia + Ventas por Punto de Venta (Local 144 / 107 / 433)
2. Inventario / Rotación — índice de cobertura general, con foco especial en **sugerencia de pedidos a proveedores**
3. Comercial / Comisiones — escalafón pendiente de definir con el negocio

## Estructura

```
config/
  sucursales.json         # Local 144 / 107 / 433
  inventario_config.json  # umbrales de cobertura para reorden a proveedores
  categoria_familia.json  # mapeo categoría Effi -> familia de producto (por completar)
  metas_comisiones.json   # metas y escalafón de comisiones (por completar)
reportes/
  raw/                    # Excel crudo descargado de Effi (gitignored)
  *.json                  # datos intermedios procesados (se generan, no se versionan a mano)
scripts/
  common/
    effi_client.py        # login, sesión, descarga de reportes (Playwright)
    procesamiento.py       # limpieza pandas, cobertura de inventario
  generar_dashboard.py    # motor de generación del HTML
  reporte_completo.py     # corrida manual completa (semanal/mensual)
  actualizar_dashboard.py # corrida automática (horaria, cron/LaunchAgent)
  verificar_sesion.py     # chequeo de sesión al encender la máquina
dashboard.html            # artefacto final estático (se publica en GitHub Pages)
```

## Credenciales

Las credenciales de Effi se guardan **cifradas en el Keychain de macOS**
(servicio `divina-intuicion-effi`), nunca en archivos del repo. La sesión
(cookies) se guarda en `~/.divina_intuicion_session.json`, fuera del repo.

## Pendientes antes de la primera corrida real

- [ ] Confirmar acceso funcional a Effi con las credenciales guardadas.
- [ ] Verificar selectores reales del login y de "Reporte de conceptos" (los actuales son un punto de partida basado en la guía genérica).
- [ ] Confirmar `nombre_effi` de cada sucursal en `config/sucursales.json`.
- [ ] Definir con el área financiera qué estados de Effi cuentan como "venta real".
- [ ] Completar `config/categoria_familia.json` con el catálogo real.
- [ ] Definir escalafón de comisiones en `config/metas_comisiones.json`.
- [ ] Crear el repo remoto `divina-intuicion-dashboard` en GitHub y activar GitHub Pages.

## Instalación

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```
