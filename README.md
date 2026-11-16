# UMBRAL

Generación gratuita en CPU de vídeo vertical 720×1280 con voz masculina española
Kokoro `em_alex`, velocidad 1,08, frases completas y subtítulos quemados. La voz
se sintetiza por frases enteras y conserva su prosodia: no se corta en cada
subtítulo, no introduce pausas arbitrarias y solo hay pausas breves al final
de las frases. Los subtítulos se distribuyen por duración de voz y longitud
de texto con detección de silencio; son estimaciones, no alineación fonética
exacta. Conviene revisar visualmente el resultado.
Se muestran como máximo dos líneas breves, con contorno y margen inferior de
235 px para dejar espacio a los controles. Los subtítulos ocupan una zona reducida;
conviene revisar visualmente cada vídeo antes de usarlo.

Las escenas de cada relato (cuatro en los antiguos y seis en los nuevos) se generan localmente con `stabilityai/sd-turbo`
(Diffusers, float32, CPU, cuatro pasos). No usa APIs de pago, claves ni GPU.
La primera ejecución descarga los modelos públicos de Hugging Face y necesita
Internet. La disponibilidad del proveedor puede hacer fallar una descarga; se
falla explícitamente en vez de sustituir las escenas por tarjetas de texto.
Revisar las condiciones de licencia de los modelos antes de distribuir contenido.
Las imágenes son generativas: los detalles y las caras pueden variar entre escenas.

La composición incorpora un zoom de cámara muy suave y una banda sonora original de terror compuesta por código: drones graves, cuerdas oscuras, melodía inquietante de piano/caja de música, ruido ambiental y pulsos lejanos. La pista está normalizada para oírse en móviles, sin tapar la voz. La música baja automáticamente durante la voz y sube ligeramente en los silencios, sin música ajena, bancos de audio ni servicios de pago.

## Generar

En Ubuntu con Python 3.11:

```sh
sudo apt-get update
sudo apt-get install -y ffmpeg espeak-ng fonts-dejavu-core libsndfile1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python render.py
```

`UMBRAL_DATE=2026-11-15` selecciona de forma reproducible el primer relato.
`UMBRAL_SPEED` permite cambiar el ritmo (predeterminado 1,08).
Los tres relatos nuevos tienen 140–170 palabras; los veinte anteriores se
conservan íntegros en `stories.archive.json` para revisión y futuras ampliaciones.
Los relatos nuevos admiten seis descripciones de escenas para mayor dinamismo; los anteriores conservan cuatro.

El workflow valida un MP4 real en cada PR y admite ejecución manual. Su artefacto
incluye MP4 H.264/AAC, voz, música original, imágenes, subtítulos ASS, relato y descripción.
La comprobación usa ffprobe (dimensiones, pistas y duración) y decodifica el vídeo
completo con FFmpeg. La prueba unitaria de codificación usa imágenes y tono de
prueba; el paso posterior ejecuta los modelos reales sin esas sustituciones.
El tiempo depende del runner: las imágenes se procesan secuencialmente para
limitar la memoria. No se contratan servicios externos; Actions está sujeto a las
cuotas gratuitas y a la configuración de facturación de la cuenta.

## Generación diaria y publicación segura

`publish_reel.py` se conserva sin ejecutar. Los tres pasos de preparación pública,
espera en Pages y publicación en Instagram tienen `if: ${{ false }}`. La generación diaria está programada en GitHub Actions a las 02:17 UTC para que el vídeo esté listo muchas horas antes de las 21:00 (Europe/Madrid). La publicación en GitHub Actions sigue bloqueada; un proceso aparte publicará usando la conexión Windsor.ai del propietario, si dispone del vídeo y relato correctos para ese mismo día. No se leen secretos de Meta durante la generación.
El token del workflow solo tiene lectura y checkout no conserva credenciales.

El relato del día siguiente se prepara por la tarde del día anterior. Los relatos destinados a la generación programada deben llevar `publish_date` con la fecha peninsular del día (`AAAA-MM-DD`) y el generador se detiene si falta el relato fechado. Se evita así publicar inadvertidamente una historia repetida. La programación diaria de GitHub solo genera el MP4 y sus artefactos: **nunca publica en Instagram**. La publicación se orquesta externamente mediante Windsor.ai/Dropbox a las 21:00 Europe/Madrid, con control de duplicados y verificación del artefacto. Cambiar `IG_PUBLISH_ENABLED` no activa publicación directa desde Actions.


## Publicación puntual a las 21:00 (Meta API oficial)

El generador nocturno del Reel está programado a las **02:17 UTC**, con mucha
antelación. La publicación autónoma va en el workflow independiente
`.github/workflows/publish_daily.yml` y se activa solo cuando estén
configurados los permisos correspondientes.

- Preparación: 17:17 UTC, con respaldo a las 18:17 UTC. Se lanza **antes**
  de las 21:00 tanto en invierno como en verano. Los dos lanzamientos
  comparten bloqueo y un registro de publicación; no deben duplicar Reels.
- El workflow verifica un Reel generado hoy, la fecha del relato, el archivo
  H.264/AAC, los subtítulos y la música de fondo original. No utiliza
  vídeos de ayer ni historias sin fecha.
- Publica un MP4 **con nombre único por día** en GitHub Pages para que Meta
  lo descargue. Solicita explícitamente un build de GitHub Pages (los pushes con GITHUB_TOKEN no lanzan builds automáticos) y comprueba que la URL sirve exactamente el archivo generado
  (SHA-256), crea el contenedor con tiempo, espera el estado FINISHED y
  lanza la orden de publicación al llegar a las **21:00 Europe/Madrid**.
- Consulta los Reels recientes mediante Instagram Graph API, adjunta una
  marca de fecha única al pie de foto y guarda recibo en
  `docs/published/AAAA-MM-DD.json`. Nunca reintenta a ciegas una
  publicación ambigua. Si se supera la ventana puntual, aborta y avisa;
  no publica un Reel tarde.
- Se necesita la **API oficial de Instagram** y un token válido autorizado
  para publicar en @umbral.terror. No se usa un navegador ni un servicio
  de pago para publicar.

### Estado operativo desde el 16/11/2026

- **IG_ACCESS_TOKEN** está guardado en GitHub Actions Secrets. La prueba oficial
  de solo lectura confirmó @umbral.terror, acceso a la cuota de publicación,
  permiso `instagram_content_publish` y fecha de caducidad del token
  **15/01/2027** (UTC). No se guarda el valor del token en este repositorio.
- **La tarea anterior «UMBRAL · Publicar Reel diario» de ChatGPT está desactivada.**
- **Publicación oficial activada:** el workflow `publish_daily.yml` solo actúa
  en eventos programados; genera una única publicación diaria a las
  **21:00 Europe/Madrid**, si pasa todas las validaciones.
- **Parada de emergencia:** configura la variable de Actions
  `UMBRAL_META_PUBLISH_ENABLED` al valor `false`. Si no está definida,
  el sistema permanece activo. También puedes deshabilitar el workflow desde
  la pestaña Actions de GitHub.
- **No publicar vídeos de prueba:** la ruta `workflow_dispatch` no autoriza
  publicaciones y la generación `reel.yml` mantiene sus pasos directos
  de Instagram bloqueados.
- La primera publicación 100 % desatendida aún debe **verificarse**: el token
  pasó validación de lectura, pero no se ha probado un POST autónomo completo.

### Mantenimiento y precauciones

- El nuevo token de Meta caduca el **15 de enero de 2027**. Renovarlo con
  antelación, actualizar el Secret de GitHub y ejecutar la validación de solo
  lectura. Sin renovación, los Reels dejarían de publicarse.
- Después de las 21:20 Europe/Madrid, la tarea ChatGPT de **verificación**,
  que no publica nada, comprueba el resultado y puede avisar de fallos.
- Antes de publicar, el workflow comprueba fecha del relato, formato de vídeo,
  música, identidad del archivo servido por Pages, procesamiento de Meta,
  y posibles duplicados mediante el registro y los medios de Instagram.
- No se puede garantizar precisión absoluta al segundo: GitHub puede
  retrasar o descartar ejecuciones cron y Meta puede tardar en mostrar el Reel.
  La preparación anticipada reduce el riesgo. Si no está listo a tiempo,
  la publicación se detiene en lugar de salir tarde.

La publicación directa heredada del generador `reel.yml` continúa bloqueada.
