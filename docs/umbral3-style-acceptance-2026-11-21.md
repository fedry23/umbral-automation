# UMBRAL 3.0 — aceptación del estilo visual · 21/11/2026

## Decisión del propietario

Tras recibir la lámina de seis fotogramas del candidato **«El banco de la parada» (22/11, 21h), versión horror-v3**, el propietario manifestó explícitamente en el chat: «A mí me gusta, con el algoritmo de aprendizaje irá mejorando, podemos darlo por valido y terminar porfin umbral».

**Decisión:** aceptar **horror-v3 como referencia de dirección artística preferida** y dejar de iterar arbitrariamente el aspecto. Se priorizan estabilidad, cierre técnico y aprendizaje incremental con métricas reales. No gastar dinero ni modificar Curio25 o JARVIS.

**Alcance exacto:** el propietario ha visto una lámina con **seis fotogramas** del candidato privado del 22/11 21h, no los fotogramas y audios de los catorce archivos previamente preparados. Esta aceptación **no constituye aprobación de los otros trece vídeos, ni habilita automáticamente la publicación de un Reel**. Las anomalías narrativas de la lámina V3 pueden seguir siendo imperfectas, pero el propietario acepta la apariencia como base.

## Evidencia técnica

- Job de seis escenas + MP4 + SHA privado: https://github.com/fedry23/umbral-automation/actions/runs/44916876326 (**SUCCESS**).
- Objeto de candidato V3: `18f8c19740611eb818eb5262010b85a73d34c1fa96667736e67eecc68b4495a3.zip`, 16.496.429 bytes, en `Fedry23/umbral-private`.
- Modelo de inferencia: SDXL Lightning, 2 pasos, backend versionado `sdxl-lightning-2steps-ov-int8-horror-v3`.
- Los catorce ZIP originales siguen almacenados, sin aprobación individual. La cuenta oficial, su publicación a las 09:00/21:00 Europe/Madrid y su mecanismo de respaldo no se alteran por este registro.

## Requisitos de despliegue que NO se deben omitir

1. Reconciliación con Meta, numeración y publicación exactamente una vez con estados inciertos.
2. Recepción de vídeo final privado, hashes verificados y gate de aprobación por bytes.
3. Reposición D+7 sin generar historias inexistentes. Fuera del horizonte 21–27/11 faltan guiones de fechas futuras.
4. Pruebas de regresión, despliegue reversible y vigilancia real tras el despliegue.

No registrar `ready_to_publish=true` ni `visual_approved=true` para todos los vídeos solo por esta aceptación del estilo. Si se desea liberar el candidato V3 concreto, su aprobación debe ligarse a la fecha, la franja, la historia y los seis SHA exactos y verificarse mediante el gate existente.
