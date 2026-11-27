# Cinematic 5.0 — operación y mantenimiento

## Estructura

- policy.json: interruptor editorial versionado. enabled=false devuelve la selección al sistema anterior.
- scheduled.json: cortes originales por fecha civil y franja (AAAA-MM-DD_09 o AAAA-MM-DD_21).
- pilots.json: tres guiones históricos de desarrollo; no forman parte de la cola oficial.
- scripts/cinematic5_policy.py: selección compartida y lectura del índice, sin red ni credenciales.
- scripts/cinematic5.py: render de cortes cortos, validación y empaquetado compatible.
- scripts/cinematic5_learning.py: comparación descriptiva a igual antigüedad; no aplica cambios automáticamente.
- render.py: intento cinematográfico cuando hay corte autorizado; recuperación del relato largo.
- scripts/umbral3_rollout.py: evita que la ruta V3.1 sustituya una fecha/franja cinematográfica.
- scripts/stage_daily_reel.py y stage_morning_reel.py: verifican índice, fecha, título y formato antes de entregar a Meta.
- scripts/publish_daily.py y reconcile_publications.py: conservan la protección de duplicados y registran render_format cuando está confirmado.

## Operación

1. Preparar versiones larga y corta juntas con antelación.
2. Mantener el número de episodio real asignado por la ruta oficial; episode_number=0 en el corte es sólo un marcador interno.
3. No reescribir fechas que ya tengan un intento persistido o recibo oficial.
4. Si el render corto no pasa las comprobaciones, conservar el original largo; nunca etiquetar ese respaldo como Cinematic 5.
5. En caso de incidente, desactivar policy.json para nuevas preparaciones y recuperar con los workflows existentes. Nunca borrar docs/pending ni repetir un POST de resultado ambiguo.
6. Confirmar el formato y la publicación mediante docs/published; la aprobación artística no se deduce de la validación técnica.
7. Mantener los horarios y las marcas de deduplicación del sistema existente. La retirada de estas marcas exige una migración coordinada y no se realiza durante este lanzamiento.
8. Medir a 24, 72 y 168 horas cuando haya observaciones reales; no inventar instantáneas pasadas ni mezclar el formato largo con el corto.

Cobertura inicial: 28/11/2026–01/12/2026, ambas franjas. Después de esa fecha, hay que ampliar scheduled.json junto a los nuevos relatos. No se garantiza el primer estreno hasta recibir un recibo real. Se mantiene la decisión del propietario de evaluar creativamente en publicaciones reales, sin renderizar pilotos adicionales.
