# Datos económicos diarios en el mismo Excel de Drive

El workflow `actualizar.yml` consulta las fuentes a las **19:05 de Argentina (22:05 UTC)**. GitHub puede demorar el inicio. Conserva el ID y nombre `Tipo_de_Cambio_BNA.xlsx` de Drive mediante el puente Apps Script ya configurado; no requiere que la Mac esté encendida. Una copia descargada no se sincroniza sola.

## Fuentes y hojas

- **Cotizaciones**: compra y venta de Dólar BNA de [El Cronista](https://www.cronista.com/MercadosOnline/dolar.html/). Se identifica exactamente `ARS=BNAR`; no se usa blue, mayorista ni MEP. El histórico anterior de cuatro series se conserva íntegro en **Histórico Errepar** al migrar. Desde entonces no se consulta Errepar. Se conserva el calendario diario: los días sin fila usan el último dato disponible y muestran su fecha efectiva y estado de arrastre. El panel actual queda como observado y sin certificación de cierre; el histórico lo reemplaza en consultas posteriores.
- **Bovespa, SP500, Merval, SSEC**: históricos diarios de Investing, con cierre, apertura, máximo, mínimo y variación. Las filas de la fecha actual son provisionales y se revisan en la siguiente consulta. Merval usa la página **MSCI Merval**; la antigua página S&P Merval dejó de actualizarse en octubre de 2026. No se empalman ambas bases. SSEC es Shanghai Composite.
- **ROFEX**: futuros simples DLR de [A3 CEM](https://cem.matbarofex.com.ar/), campo `settlement` (ajuste oficial), incluyendo contratos sin volumen. Cada rueda conserva el mes actual y los doce siguientes: octubre de 2026 hasta octubre de 2027 inclusive son 13 posiciones. Se guarda fecha de rueda, contrato, mes y ajuste en ARS/USD. Un mes no publicado queda vacío con estado explícito. No se interpola ni se sustituye por el último negociado.
- **SOFR**: tasa overnight anual de la [Reserva Federal de Nueva York](https://www.newyorkfed.org/markets/reference-rates/sofr/), obtenida de su API oficial. Se guarda fecha efectiva y revisiones. No es Term SOFR ni los promedios a 30/90/180 días. Se almacena como porcentaje Excel real.
- **Fuente**: cinco renglones de metadatos y estado de la última consulta, según la preferencia del usuario.

La primera consulta toma aproximadamente un mes de historia disponible. Después combina por fecha (y contrato en ROFEX), revisa un solapamiento reciente y conserva el historial. No es una descarga de historia completa. Si BNA o un índice no solapa con el historial del libro después de una inactividad prolongada, conserva esa hoja e informa el hueco para recuperarlo expresamente.

## Errores y conservación

Las fuentes se validan por separado. Una fuente fallida conserva su hoja anterior; las correctas se actualizan. La hoja Fuente informa los errores y Actions termina con error **después** de guardar la actualización parcial, para que el fallo no pase inadvertido. Si ninguna fuente valida, no se modifica ni se sube el libro. Un bloqueo de Excel cancela la actualización. Hay respaldo antes del reemplazo atómico y control de versión antes de publicar en Drive. Evitá editar el archivo mientras corre.

Se conservan HTML/JSON, fecha de captura y URL de cada consulta en `evidencia/`, y respaldos en `respaldos/`, disponibles como artefactos de Actions durante 30 días. Investing puede bloquear accesos automáticos: se intenta una navegación normal con Chromium, sin resolver desafíos ni eludir bloqueos. Si persiste, se informa y se conserva la última hoja correcta.

## Uso y pruebas

```sh
python -m pip install -r requirements-cloud.txt
python -m playwright install --with-deps chromium
python -m unittest -v test_economicos test_apps_script test_cloud
python actualizar_economicos.py --book copia-de-prueba.xlsx
```

El archivo de prueba debe existir. Los scripts de Drive descargan primero el libro vigente y usan el mismo actualizador. La opción manual **comprobar_fuente** del workflow consulta en el runner sin acceder a Drive. El workflow **Probar nuevas fuentes económicas** prueba una copia aislada sin secretos ni escritura en Drive.

La configuración Apps Script existente usa los secretos `APPS_SCRIPT_URL` y `APPS_SCRIPT_KEY`; no se imprimen ni se guardan en el repositorio. Para reinstalar el puente, ver `google-apps-script/INSTRUCCIONES.md`. La alternativa OAuth anterior permanece disponible, pero no es necesaria para la configuración actual. Los scripts `actualizar_oficial.py` y `actualizar_bna.py` quedan como compatibilidad histórica y pruebas: el workflow diario invoca `actualizar_economicos.py` a través del puente.
