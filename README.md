# Datos económicos diarios en el mismo Excel de Drive

El workflow `actualizar.yml` consulta las fuentes a las **19:05 de Argentina (22:05 UTC)**, con consultas de respaldo a las **19:35 y 20:05**. GitHub puede demorar u omitir ejecuciones programadas; estos horarios no garantizan puntualidad. Las consultas se serializan para evitar ejecuciones simultáneas y revisan las correcciones publicadas por las fuentes. Conserva el ID y nombre `Tipo_de_Cambio_BNA.xlsx` de Drive mediante el puente Apps Script ya configurado; no requiere que la Mac esté encendida. Una copia descargada no se sincroniza sola.

## Fuentes y hojas

- **Cotizaciones**: compra y venta de Dólar BNA de [El Cronista](https://www.cronista.com/MercadosOnline/dolar.html/). Se identifica exactamente `ARS=BNAR`; no se usa blue, mayorista ni MEP. El histórico anterior de cuatro series se conserva íntegro en **Histórico Errepar** al migrar. Desde entonces no se consulta Errepar. Se conserva el calendario diario: los días sin fila usan el último dato disponible y muestran su fecha efectiva y estado de arrastre. El panel actual queda como observado y sin certificación de cierre; el histórico lo reemplaza en consultas posteriores.
- **Bovespa, SP500 y SSEC**: cierres diarios de Yahoo Finance, símbolos `^BVSP`, `^GSPC` y `000001.SS`. Se valida identidad, tipo índice y fecha en la zona horaria del mercado. Las filas del día son provisionales y se revisan en la siguiente consulta. SSEC es Shanghai Composite.
- **Merval**: cierres de MSCI Merval desde la API pública oficial de BYMA. Se utiliza el código histórico M, conservando solo el tramo desde el 19/10/2026 para no empalmarlo con el antiguo S&P Merval. Los ceros publicados por BYMA en la transición se muestran como faltantes, nunca como caídas de 100%.
- **ROFEX**: futuros simples DLR de [A3 CEM](https://cem.matbarofex.com.ar/), campo `settlement` (ajuste oficial), incluyendo contratos sin volumen. Cada rueda conserva el mes actual y los doce siguientes: octubre de 2026 hasta octubre de 2027 inclusive son 13 posiciones. Se guarda fecha de rueda, contrato, mes y ajuste en ARS/USD. Un mes no publicado queda vacío con estado explícito. No se interpola ni se sustituye por el último negociado.
- **SOFR**: tasa overnight anual de la [Reserva Federal de Nueva York](https://www.newyorkfed.org/markets/reference-rates/sofr/), obtenida de su API oficial. Se guarda fecha efectiva y revisiones. No es Term SOFR ni los promedios a 30/90/180 días. Se almacena como porcentaje Excel real.
- **Fuente**: cinco renglones de metadatos y estado de la última consulta, según la preferencia del usuario.

La primera consulta toma aproximadamente un mes de historia disponible. Después combina por fecha (y contrato en ROFEX), revisa un solapamiento reciente y conserva el historial. No es una descarga de historia completa. Si BNA no solapa con el historial del libro después de una inactividad prolongada, conserva esa hoja e informa el hueco para recuperarlo expresamente.

## Errores y conservación

Las fuentes se validan por separado. Una fuente fallida conserva su hoja anterior; las correctas se actualizan. La hoja Fuente informa los errores y Actions termina con error **después** de guardar la actualización parcial, para que el fallo no pase inadvertido. Si ninguna fuente valida, no se modifica ni se sube el libro. Un bloqueo de Excel cancela la actualización. Hay respaldo antes del reemplazo atómico y control de versión antes de publicar en Drive. Evitá editar el archivo mientras corre.

Se conservan HTML/JSON, fecha de captura y URL de cada consulta en `evidencia/`, y respaldos en `respaldos/`, disponibles como artefactos de Actions durante 30 días. Investing rechazó las consultas desde GitHub incluso con navegación normal. El usuario autorizó otras fuentes verificables para mantener la actualización con la Mac apagada. Se eligió Yahoo para los tres índices internacionales y BYMA para el Merval vigente; cada hoja identifica su fuente real. No se etiquetan como datos de Investing.


## Uso y pruebas

Para agregar un pedido diario independiente desde Google alrededor de las 20:00 de Argentina, seguir [Segundo programador en Apps Script](google-apps-script/PROGRAMADOR.md). Requiere instalar el archivo adicional y autorizar un token de GitHub en las propiedades del proyecto; publicar este código no instala el disparador.

```sh
python -m pip install -r requirements-cloud.txt
python -m playwright install --with-deps chromium
python -m unittest -v test_economicos test_apps_script test_cloud
python actualizar_economicos.py --book copia-de-prueba.xlsx
```

El archivo de prueba debe existir. Los scripts de Drive descargan primero el libro vigente y usan el mismo actualizador. La opción manual **comprobar_fuente** del workflow consulta en el runner sin acceder a Drive. El workflow **Probar nuevas fuentes económicas** prueba una copia aislada sin secretos ni escritura en Drive.

La configuración Apps Script existente usa los secretos `APPS_SCRIPT_URL` y `APPS_SCRIPT_KEY`; no se imprimen ni se guardan en el repositorio. Para reinstalar el puente, ver `google-apps-script/INSTRUCCIONES.md`. La alternativa OAuth anterior permanece disponible, pero no es necesaria para la configuración actual. Los scripts `actualizar_oficial.py` y `actualizar_bna.py` quedan como compatibilidad histórica y pruebas: el workflow diario invoca `actualizar_economicos.py` a través del puente.

## Fecha de consulta y fecha del dato

Una consulta exitosa no garantiza un valor de la misma fecha. El reporte y Fuente muestran por serie la última fecha con valor y los datos pendientes de la fecha consultada; SOFR conserva su fecha efectiva de publicación, sin exigir la del día de consulta.

Si Yahoo todavía no completa la vela histórica del día, se admite su regularMarketPrice únicamente con regularMarketTime de esa misma fecha en la zona horaria del mercado. Se identifica como cotización de referencia e histórico pendiente; nunca se traslada una cotización anterior a hoy. Para MSCI Merval, cuando el histórico oficial está retrasado se consulta también index-price de BYMA, seleccionando MMSCI y su closingPrice fechado, no trade ni previousClosingPrice.
