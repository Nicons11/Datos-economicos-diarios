# Activar Datos Financieros conservando el mismo archivo y programador

La nueva versión se prepara en la rama `codex/datos-financieros` y primero se valida en una copia sin escribir en Drive. Para poder renombrar el archivo manteniendo su ID, el puente de Apps Script necesita esta actualización única. La tarea de GitHub no puede editar el proyecto de Google con la autorización actual.

1. En tu proyecto **Excel diario** de Apps Script, abrí **Código.gs**. Copiá todo `google-apps-script/Codigo.gs` de la nueva versión y reemplazá únicamente el contenido de **Código.gs**. Guardá. Conservá **Programador.gs**, sus activadores y las propiedades `CLAVE_GITHUB` y `TOKEN_GITHUB`.
2. Tocá **Implementar → Administrar implementaciones**. Seleccioná la implementación web que ya existe y pulsá el lápiz **Editar**. En **Versión**, elegí **Nueva versión**, y luego **Implementar**. Conservá ejecutar como **Yo** y acceso **Cualquier usuario**. No crees otra implementación: se mantiene la URL y no hay que cambiar secretos GitHub.
3. Avisá que terminaste. Se puede leer la respuesta `fileName` para confirmar la versión del puente, activar el actualizador nuevo y ejecutar la prueba completa con guardado en Drive.

El puente reconoce tanto `Tipo_de_Cambio_BNA.xlsx` como `Datos Financieros.xlsx`. Si encuentra ambos, cancela antes de sobrescribir: no elige uno por suposición. Al guardar correctamente, renombra el archivo a **Datos Financieros.xlsx**, conservando el ID y enlace. Si todavía no está actualizado el puente, el cliente nuevo cancela antes de modificar Drive y muestra la instrucción de actualización.

La migración conserva las otras hojas y el histórico completo de Errepar, elimina ROFEX por pedido del usuario y guarda primero un respaldo del libro anterior. Errepar se actualiza en la hoja **Errepar**; FOREX, Cauciones y Riesgo país tienen hojas propias. Los fallos de fuente conservan la hoja anterior e informan el error. La TEA de Cauciones se calcula, no se presenta como publicada por MAE.
