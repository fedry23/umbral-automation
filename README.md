# UMBRAL

Generación gratuita en CPU de vídeo vertical 720×1280 con voz masculina española
Kokoro `em_alex`, velocidad 0,82, pausas y subtítulos quemados. Cada subtítulo
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
`UMBRAL_SPEED` permite cambiar el ritmo (predeterminado 0,82).
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

## Publicación y horario: preparados, DESACTIVADOS

`publish_reel.py` se conserva sin ejecutar. Los tres pasos de preparación pública,
espera en Pages y publicación en Instagram tienen `if: ${{ false }}`. El cron diario
`0 18 * * *` se conserva comentado. No se leen secretos de Meta durante la generación.
El token del workflow solo tiene lectura y checkout no conserva credenciales.

Solo tras autorización expresa del propietario se debe restaurar el evento
`schedule`, habilitar las condiciones de los tres pasos de publicación y conceder
los permisos/credenciales necesarios para el push a Pages. Cambiar únicamente
`IG_PUBLISH_ENABLED` no activa nada. Este PR no integra ni publica automáticamente.
