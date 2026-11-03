# Datos Financieros · Actualización diaria en el mismo Excel de Drive

**Versión activada y verificada el 3/11/2026.** La [ejecución completa](https://github.com/Nicons11/Datos-economicos-diarios/actions/runs/41573838179) guardó y verificó el contenido en Drive. La [lectura posterior independiente](https://github.com/Nicons11/Datos-economicos-diarios/actions/runs/41573955361) confirmó el nombre **Datos Financieros.xlsx**, las hojas nuevas, el histórico de Errepar y la ausencia de ROFEX.

El workflow `actualizar.yml` consulta las fuentes a las **19:05 de Argentina (22:05 UTC)**, con consultas de respaldo a las **19:35 y 20:05**. GitHub puede demorar u omitir ejecuciones programadas; estos horarios no garantizan puntualidad. Las consultas se serializan para evitar ejecuciones simultáneas. El puente reconoce el nombre anterior y renombra el libro a **Datos Financieros.xlsx** conservando el ID y enlace de Drive; no requiere que la Mac esté encendida. Una copia descargada no se sincroniza sola. **La migración requiere actualizar una vez la implementación existente de Apps Script siguiendo [estos pasos](google-apps-script/ACTUALIZAR_NOMBRE.md)**. No se cambian claves ni el programador de Google. El cliente nuevo rechaza la implementación anterior antes de modificar Drive.

## Fuentes y hojas

- **Cotizaciones**: compra y venta de Dólar BNA de [El Cronista](https://www.cronista.com/MercadosOnline/dolar.html/), identificado exactamente como `ARS=BNAR`. Se conserva el calendario diario, su fecha efectiva y estado de arrastre. El panel se identifica como observado sin certificar cierre.
- **Errepar**: se retoma la consulta diaria de las cuatro series BNA (billete/divisa, compra/venta) en [Errepar](https://www.errepar.com/cotizacion-dolar). La hoja anterior **Histórico Errepar** se integra a **Errepar**, conservando su historia por fecha. La captura del día queda provisional. Nunca se sustituye esta fuente por Cronista ni se reutiliza evidencia vieja como consulta actual.
- **Riesgo país**: serie argentina de [Ámbito](https://www.ambito.com/contenidos/riesgo-pais.html), en **puntos básicos**, con la fecha publicada. Se consulta su histórico público mediante navegación normal. No se rellena un día ausente con el anterior ni se divide por cien.
- **FOREX**: [MAE histórico](https://marketdata.mae.com.ar/forex/historico), total diario del campo **VOLUMEN** dividido por un millón. A = Fecha, B = USD M, con un decimal como la referencia. No se utiliza el campo MONTO en pesos. Se conserva el valor subyacente sin redondearlo al almacenarlo.
- **Cauciones**: [MAE histórico](https://marketdata.mae.com.ar/cauciones/historico), **CAARS en pesos**, menor plazo publicado entre 1 y 4 días; los viernes se observa plazo 003 hasta el lunes. A = Fecha, B = TNA% (t+1), C = TEA% (t+1), D = plazo de origen en días. Se usa **VWAP / tasaPP**, nunca última tasa. TEA equivalente diaria calculada como `(1 + TNA/365)^365 - 1`, reproduciendo la referencia; no se presenta como TEA publicada por MAE ni como rendimiento efectivo del contrato de varios días. Se añaden estado y captura. El 26/10/2026 reproduce 20,71% y 23,01%; el viernes 23/10 reproduce 20,57% y 22,83%.
- **Bovespa, SP500 y SSEC**: cierres diarios de Yahoo Finance, símbolos `^BVSP`, `^GSPC` y `000001.SS`. Se valida identidad, tipo índice y fecha en la zona horaria del mercado. Las filas del día son provisionales y se revisan en la siguiente consulta. SSEC es Shanghai Composite.
- **Merval**: cierres de MSCI Merval desde la API pública oficial de BYMA. Se utiliza el código histórico M, conservando solo el tramo desde el 19/10/2026 para no empalmarlo con el antiguo S&P Merval. Los ceros publicados por BYMA en la transición se muestran como faltantes, nunca como caídas de 100%.
- **SOFR**: tasa overnight anual de la [Reserva Federal de Nueva York](https://www.newyorkfed.org/markets/reference-rates/sofr/), obtenida de su API oficial. Se guarda fecha efectiva y revisiones. No es Term SOFR ni los promedios a 30/90/180 días. Se almacena como porcentaje Excel real.
- **Fuente**: cinco renglones de metadatos y estado de la última consulta, según la preferencia del usuario.

**ROFEX se elimina del libro y deja de consultarse**, por pedido del usuario. El respaldo anterior a la migración conserva su contenido.

La primera consulta toma aproximadamente un mes de historia disponible. Después combina por fecha, revisa un solapamiento reciente y conserva el historial. No es una descarga de historia completa. Si BNA no solapa con el historial del libro después de una inactividad prolongada, conserva esa hoja e informa el hueco para recuperarlo expresamente.

## Errores y conservación

Las fuentes se validan por separado. Una fuente fallida conserva su hoja anterior; las correctas se actualizan. La hoja Fuente informa los errores y Actions termina con error **después** de guardar la actualización parcial, para que el fallo no pase inadvertido. Si ninguna fuente valida, no se modifica ni se sube el libro. Un bloqueo de Excel cancela la actualización. Hay respaldo antes del reemplazo atómico y control de versión antes de publicar en Drive. Evitá editar el archivo mientras corre.

Se conservan HTML/JSON, fecha de captura y URL de cada consulta en `evidencia/`, y respaldos en `respaldos/`, disponibles como artefactos de Actions durante 30 días. Investing rechazó las consultas desde GitHub incluso con navegación normal. El usuario autorizó otras fuentes verificables para mantener la actualización con la Mac apagada. Se eligió Yahoo para los tres índices internacionales y BYMA para el Merval vigente; cada hoja identifica su fuente real. No se etiquetan como datos de Investing.


## Uso y pruebas

Para agregar un pedido diario independiente desde Google alrededor de las 20:00 de Argentina, seguir [Segundo programador en Apps Script](google-apps-script/PROGRAMADOR.md). Requiere instalar el archivo adicional y autorizar un token de GitHub en las propiedades del proyecto; publicar este código no instala el disparador.

```sh
python -m pip install -r requirements-cloud.txt
python -m playwright install --with-deps chromium
python -m unittest -v test_financieros test_economicos test_apps_script test_cloud
python actualizar_economicos.py --book copia-de-prueba.xlsx
```

El archivo de prueba debe existir. Los scripts de Drive descargan primero el libro vigente y usan el mismo actualizador. La opción manual **comprobar_fuente** del workflow consulta en el runner sin acceder a Drive. El workflow **Probar nuevas fuentes económicas** prueba una copia aislada sin secretos ni escritura en Drive.

La configuración Apps Script existente usa los secretos `APPS_SCRIPT_URL` y `APPS_SCRIPT_KEY`; no se imprimen ni se guardan en el repositorio. Para reinstalar el puente, ver `google-apps-script/INSTRUCCIONES.md`. La alternativa OAuth anterior permanece disponible, pero no es necesaria para la configuración actual. Los scripts `actualizar_oficial.py` y `actualizar_bna.py` quedan como compatibilidad histórica y pruebas: el workflow diario invoca `actualizar_economicos.py` a través del puente.

## Fecha de consulta y fecha del dato

Una consulta exitosa no garantiza un valor de la misma fecha. El reporte y Fuente muestran por serie la última fecha con valor y los datos pendientes de la fecha consultada; SOFR conserva su fecha efectiva de publicación, sin exigir la del día de consulta.

Si Yahoo todavía no completa la vela histórica del día, se admite su regularMarketPrice únicamente con regularMarketTime de esa misma fecha en la zona horaria del mercado. Se identifica como cotización de referencia e histórico pendiente; nunca se traslada una cotización anterior a hoy. Para MSCI Merval, cuando el histórico oficial está retrasado se consulta también index-price de BYMA, seleccionando MMSCI y su closingPrice fechado, no trade ni previousClosingPrice.
