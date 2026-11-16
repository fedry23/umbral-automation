# UMBRAL

Generación gratuita en CPU de vídeo vertical 720×1280 con voz masculina española
Kokoro `em_alex`, velocidad 0,86, pausas y subtítulos quemados. Cada subtítulo
se sintetiza por separado: sus tiempos se calculan a partir de las muestras de
ese mismo audio, incluidas las pausas; no se estiman por número de palabras.
Se muestran como máximo dos líneas breves, con contorno y margen inferior de
235 px para dejar espacio a los controles. Los subtítulos ocupan una zona reducida;
conviene revisar visualmente cada vídeo antes de usarlo.

Las cuatro escenas de cada relato se generan localmente con `stabilityai/sd-turbo`
(Diffusers, float32, CPU, cuatro pasos). No usa APIs de pago, claves ni GPU.
La primera ejecución descarga los modelos públicos de Hugging Face y necesita
Internet. La disponibilidad del proveedor puede hacer fallar una descarga; se
falla explícitamente en vez de sustituir las escenas por tarjetas de texto.
Revisar las condiciones de licencia de los modelos antes de distribuir contenido.
Las imágenes son generativas: los detalles y las caras pueden variar entre escenas.

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
`UMBRAL_SPEED` permite cambiar el ritmo (predeterminado 0,86).
Los tres relatos nuevos tienen 140–170 palabras; los veinte anteriores se
conservan íntegros en `stories.archive.json` para revisión y futuras ampliaciones.
Cada relato incluye cuatro descripciones de escenas en orden narrativo.

El workflow valida un MP4 real en cada PR y admite ejecución manual. Su artefacto
incluye MP4 H.264/AAC, voz, imágenes, subtítulos ASS, relato y descripción.
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
