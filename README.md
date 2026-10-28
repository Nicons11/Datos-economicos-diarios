# Excel BNA diario en Google Drive

GitHub Actions ejecuta `actualizar_drive.py` todos los días a las **19:05 de Argentina** (22:05 UTC), aunque tu Mac esté apagada. GitHub puede demorar el inicio: no es un horario garantizado. El workflow ya está publicado y activo; falta configurar la autorización y la carpeta de Drive para completar las actualizaciones remotas. Guardar el entorno de Codex no sustituye esa autorización.

La ejecución [40618043814](https://github.com/Nicons11/Datos-economicos-diarios/actions/runs/40618043814) pasó las ocho pruebas y la consulta real a Errepar con actualización del libro local del runner. No accedió a Drive. Para repetir esa comprobación, usá Run workflow y activá `comprobar_fuente`; para el flujo completo dejá esa opción desactivada.

## Qué hace

Busca `Tipo_de_Cambio_BNA.xlsx` en la carpeta elegida. Si existe, descarga esa versión, consulta Errepar y actualiza el mismo archivo de Drive conservando su enlace. Si no existe, usa el Excel inicial adjunto y lo crea después de una consulta exitosa. No convierte el libro a Google Sheets.

Conserva las cuatro series, historial, fechas efectivas y marcas de datos provisionales. Si falla la extracción no sube un archivo nuevo. Guarda evidencia y respaldo previo durante 30 días en los artefactos de GitHub Actions. Evitá editar el libro mientras corre: se comprueba su versión antes de subir, pero esa comprobación no es un bloqueo de edición en Drive. Una copia descargada a tu Mac no se sincroniza sola; abrí el archivo de Drive o usá Drive para escritorio.

## Activar una vez

1. El contenido ya está publicado en la rama `main` de `Nicons11/Datos-economicos-diarios` y Actions está activo. Nunca subas tokens o credenciales al repositorio.
2. La carpeta de Drive proporcionada por el usuario ya está configurada como destino predeterminado en el workflow. Podés dejarla vacía o subir el Excel inicial sin convertirlo ni cambiar el nombre. No debe haber dos archivos con ese nombre. Para cambiarla, configurá `GOOGLE_DRIVE_FOLDER_ID` con el ID de otra carpeta (`.../folders/ID`). El ID identifica la ubicación y no concede acceso.
3. En Google Cloud, habilitá **Google Drive API**. Configurá el consentimiento OAuth y creá un cliente OAuth de tipo **Aplicación de escritorio**. Descargá su JSON fuera del repositorio. La autorización solicita acceso a Drive para buscar, leer y actualizar el archivo; usá una cuenta dedicada si preferís limitar el alcance a esa cuenta. Si tu organización restringe OAuth, necesitarás su autorización.
4. En tu computadora, con Python 3.10 o posterior, instalá `python3 -m pip install -r requirements-cloud.txt`. Ejecutá una única vez `python3 autorizar_drive.py /ruta/cliente.json /ruta/privada/token-drive.json`. Se abre Google para autorizar. Elegí una ruta de salida fuera del repositorio. No compartas ese archivo ni lo pegues en el chat.
5. En GitHub → Settings → Secrets and variables → Actions, creá el **secret** `GOOGLE_DRIVE_CREDENTIALS_JSON` con el contenido del archivo privado generado. La variable `GOOGLE_DRIVE_FOLDER_ID` es opcional: solo se necesita para reemplazar la carpeta ya configurada. Nunca guardes el token como variable pública.
6. En Actions → **Actualizar Excel en Google Drive** → **Run workflow**, hacé la primera ejecución. Confirmá que finalice correctamente y que aparezca el Excel en Drive. A partir de entonces el cron diario queda activo. Si el repositorio es público, GitHub puede deshabilitar cron tras 60 días sin actividad; revisá el estado periódicamente.

Importante: los refresh tokens de una app OAuth externa en estado **Testing** suelen vencer a los siete días con el alcance Drive. Configurá una modalidad de producción o interna compatible con tu cuenta y los requisitos de Google antes de depender de la tarea diaria. Si se revoca o vence la autorización, regenerá el secreto. Los errores aparecen en Actions; configurá las notificaciones de GitHub para recibir fallos.

## Desarrollo y comprobaciones

```sh
python3 -m venv /workspace/bna-venv
/workspace/bna-venv/bin/python -m pip install -r requirements-cloud.txt
/workspace/bna-venv/bin/python -m playwright install chromium
/workspace/bna-venv/bin/python -m unittest -v test_cloud test_bna.Rules.test_exact_previous_order_duplicates_and_ignore_extra test_bna.Rules.test_unavailable_invalid_blank_future_and_today test_bna.Rules.test_parse test_bna.Rules.test_source_validation
```

`python actualizar_oficial.py` consulta y actualiza solo el libro local. `python actualizar_drive.py` realiza el flujo completo y requiere las dos variables indicadas. Playwright necesita Chromium y sus bibliotecas de sistema; el workflow instala ambos con `--with-deps`.

Las pruebas originales `test_oficial.py` y un caso de `test_bna.py` requieren archivos históricos no adjuntos (`evidencia/inicio_oficial/fuente.json`, `evidencia/fuente_verificada.json` y `BNA_independiente.xlsx`). No se fabrican esas evidencias. Las nuevas pruebas usan datos sintéticos en copias temporales y verifican guardado, respaldo, historial, rechazo de capturas viejas y ausencia de publicación al fallar. No sustituyen una primera ejecución real contra Errepar y Drive.

Servicios necesarios: Errepar, Google Drive y OAuth de Google; las instalaciones también requieren PyPI y los servidores de Chromium de Playwright. No se consulta VPN ni un archivo empresarial. Esta automatización es independiente de cualquier tarea local anterior: desactivá la antigua cuando la ejecución en Drive esté validada.
