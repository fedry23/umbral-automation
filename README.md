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

## Episodios con intro, outro y miniatura de marca

Cada nuevo Reel de UMBRAL tiene tres tramos visuales **independientes**:

- **Intro:** escenario animado de arquitectura en perspectiva, puerta roja, niebla y partículas, con un umbral luminoso, número del episodio (fijo) y título; narrador con voz ~3 semitonos más grave.
- **Historia:** seis escenas AI originales del guion, con la **voz masculina habitual sin alterar**, subtítulos y música tétrica propia.
- **Outro:** pasillo animado azul-negro con puerta que gira hasta cerrarse, el cierre **«Has cruzado el umbral. Y ahora... no mires atrás»** y voz grave, distinta de la historia y de la intro.

El motor calcula los límites de audio exactos en `output/branding_timing.json` y superpone dos clips animados originales a los tramos de marca; las tarjetas PNG quedan como vistas previas de compatibilidad para que nunca aparezcan las ilustraciones del relato detrás de la intro o la outro.

Cada Reel recibe `output/cover.jpg` **JPEG RGB de 1080×1920**, basada en una escena del propio episodio y sobreimpresa con UMBRAL, número y título en la zona central legible también en la cuadrícula del perfil. El publicador diario recupera la portada desde los artefactos, valida JPEG y tamaño, copia MP4 y JPEG a GitHub Pages, comprueba SHA-256 de ambos archivos y envía `cover_url` a Meta en el contenedor REELS antes de publicar. Si falta una portada válida o se rechaza el contenedor, el flujo falla explícitamente en lugar de publicar a ciegas.

El generador hace un control final H.264, yuv420p, 9:16, 23–60 FPS y AAC a 48 kHz; el publicador conserva una reparación automática y segura de audio para material antiguo. No requiere API gráfica de pago ni imágenes ajenas.

`quality_gate.yml` valida en GitHub Actions sintaxis, portada, tarjetas, voz, formatos y duplicados sin conectar a Meta ni publicar. Las publicaciones ya realizadas **no se modifican retroactivamente** por estos cambios.

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

`reel.yml` genera los vídeos y nunca publica Instagram: sus tres antiguos pasos de preparación pública, Pages y publicación permanecen en `if: ${{ false }}`. Su cron sigue a las 02:17 UTC, y también admite un disparo de respaldo por `push` limitado a `ops/generate-kick.txt`. La publicación real se realiza mediante el workflow INDEPENDIENTE `publish_daily.yml` y la API oficial de Meta (véase abajo). No se leen secretos de Meta durante la generación. El token del workflow de generación solo tiene lectura y checkout no conserva credenciales.

El relato del día siguiente se prepara por la tarde del día anterior. Los relatos destinados a la generación programada deben llevar `publish_date` con la fecha peninsular del día (`AAAA-MM-DD`) y el generador se detiene si falta el relato fechado. Se evita así publicar inadvertidamente una historia repetida. El workflow `reel.yml` genera el MP4 y sus artefactos: **nunca publica en Instagram**. `publish_daily.yml` lo recupera y publica mediante la API oficial de Meta a las 21:00 Europe/Madrid, comprobando fecha, formato, URL pública y duplicados. Cambiar `IG_PUBLISH_ENABLED` no activa publicación directa en el generador.


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

## Respaldo contra omisiones del cron de GitHub (desde 16/11/2026)

Los horarios `schedule` pueden retrasarse u omitirse. Para no depender de ellos como única vía, ambos workflows permiten un disparo `push` limitado a su propio archivo `ops/*-kick.txt` en `main`:

- `reel.yml`: `ops/generate-kick.txt` (no publica en Instagram).
- `publish_daily.yml`: `ops/publish-kick.txt` (prepara el contenedor y espera hasta las 21:00 locales; nunca publica tarde).

La automatización ChatGPT existente **UMBRAL · Respaldos y verificación** comprueba a las **06:20** si falta la generación del día, a las **18:20** si falta el arranque del publicador y a las **21:20** si consta un recibo de publicación (siempre hora Europe/Madrid). Solo modifica el archivo disparador correspondiente cuando faltan sus requisitos. No se deben activar publicaciones alternativas ni repetir Reels a ciegas. El recibo `docs/published/AAAA-MM-DD.json` y la consulta a Instagram son la protección contra duplicados.

El 16/11/2026 se verificó con un push de prueba que `publish_daily.yml` arranca y respeta la guarda que impide publicar después de las 20:40 si no estaba preparado. También se comprobó el arranque del generador por push; la ejecución completa y la primera publicación autónoma deben seguir validándose a partir de sus runs y recibos reales.


## Actualización cinematográfica (16/11/2026)

`scripts/brand_animation.py` renderiza fotogramas originales a 24 FPS: geometría
proyectada desde una cámara móvil, hojas de puerta con giro independiente,
niebla multicapa, partículas, reflejos y tipografía con aparición gradual.
Intro roja y outro azul se generan sin utilizar imágenes del relato. Es CGI
procedural en CPU, no vídeo generativo fotorrealista. La duración proviene del
WAV real: no hay cortes de voz. `audio_engine.py` permanece sin modificaciones.
Los dos clips se guardan en `output/branding/`; el MP4 final mantiene 720×1280,
H.264 yuv420p, AAC 48 kHz. La música agrega aire/bisagra sintetizados discretos.

La publicación utiliza una portada JPEG distinta por episodio. Se comprueba
su descarga exacta desde Pages antes de enviar `cover_url`. Tras publicar se
consulta el medio por ID, `permalink`, tipo REELS y `thumbnail_url`; la imagen
que devuelve Meta se compara con la portada local tras normalizar tamaño y
recorte. Una discrepancia queda registrada como fallo de verificación y NO
provoca una segunda publicación. El recibo se conserva aunque falle esa lectura.

Antes del POST irreversible, el publicador guarda y sube un intento en
`docs/pending/`. Un intento sin resolver bloquea otro POST incluso tras reiniciar
el runner. Los recibos están en `docs/published/`; no borrar un intento para
reintentar sin consultar antes los medios y el contenedor en Meta. El token,
la identidad y el permiso de publicación se revisan antes de crear el contenedor;
se avisa al quedar menos de diez días y se bloquea si queda menos de un día.
Los fallos quedan en Actions y los recibos/diagnóstico se conservan como artefactos.
La tarea externa de las 21:20 comunica la ausencia de confirmación.

Prueba extraordinaria única: episodio 6 «La luz del rellano», separado de la
cola diaria. `cinematic_test.yml` solo renderiza. `cinematic_publish.yml` requiere
un push a `ops/cinematic-publish.json` que identifique el run exitoso revisado y
la fecha autorizada. Usa el mismo bloqueo de concurrencia que el publicador diario,
recibo `test-cinematic-episode-6.json` e intento persistente exclusivo. No tiene cron
ni autorización para otros episodios. No reutilizar el disparador de la prueba 4.
El episodio 5 conserva su fecha 17/11; la numeración identifica episodios y no
implica que una prueba extraordinaria se publique en orden cronológico.

La preparación diaria, verano/invierno y respaldos se mantienen. GitHub/Meta
pueden retrasarse: pasada la ventana se aborta, se informa y no se publica tarde.
La nueva prueba y sus comprobaciones se documentarán con IDs reales al terminar.
