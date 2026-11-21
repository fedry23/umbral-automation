# UMBRAL 3.0 — continuidad verificada del 21 de noviembre de 2026

**Este documento registra hechos y código real, NO una aprobación ni un despliegue definitivo.**
No fusionar PR #18 ni activar media experimental en producción hasta revisar visualmente los 14 Reels completos, verificar la numeración definitiva, habilitar OIDC estricto para main y pasar pruebas end-to-end. No alterar Curio25/JARVIS, no gastar dinero, no publicar pruebas en Meta.

## Producción preservada

- Las publicaciones del 20 de noviembre quedaron confirmadas y sus recibos preservados; no reintentar POST de Meta inciertos.
- PR #20 de recuperación de artefactos fusionada en main: fd2c7601c7e4aff6c881ba920e3ec34891be2913.
- PR #22 con 12 historias futuras 22-27 noviembre fusionada en main: 675fe8bda580f2b1cf6e98fd24cc3039be618339.
- El 21/11, ante ausencia de ejecución nocturna visible, se disparó generación **sin publicar**:
  - Mañana, run 44861138625, job completado success.
  - Noche, run 44861179546, job completado success.
- Los workflows de publicación lanzados muy temprano (44862043523 y 44862063016) informaron **salto por estar fuera de la ventana horaria**. Su estado 'success' no significa que hayan publicado. Verificar recibos nuevos y lectura Meta a las horas previstas; mantener 09:00 y 21:00 Europe/Madrid.

## Almacenamiento privado

- Hugging Face bucket privado: Fedry23/umbral-private, sin prewarming ni pago.
- Trusted Publisher OIDC **solo integration/umbral-3 + workflow umbral3_hf_storage.yml**. No presupongas permiso para main.
- Tres Reels completos de prueba, no aprobados, guardados como ZIPs v2 cifrados en transporte y privados con manifest de SHA-256 en run 44821897573. Un runner nuevo validó 8 objetos, 3 full_media_v2, 0 corruptos, ready_reels=0 (run 44830532281).
- Auditoría real de 14 candidatos: scripts/umbral3_hf_candidate_audit.py; distingue candidatos recuperables de Reels aprobados. No imprimir media privada ni exponer URLs de descarga en repositorio público.
- Índices inmutables de candidato por fecha/slot/backend: scripts/umbral3_hf_candidate_index.py. Guardado y lectura SHA con recuperación tras respuesta ambigua; rechazar colisiones y cambios silenciosos.
- Ficheros privados individuales para inspección audiovisual: scripts/umbral3_hf_review_preview.py (vídeo, portada y contact_sheet), integrados con scripts/umbral3_hf_persist_candidate.py. Nunca publicarlos como artefactos públicos.
- Restauración desde un runner distinto: scripts/umbral3_hf_restore_candidate.py, SHA por fotograma, identidad de episodio, hora y autoría.

## Motor visual y montaje

- SDXL estándar INT8 ~765 s/fotograma, muy lento. FLUX INT8 no completó la prueba de viabilidad.
- **SDXL Lightning de dos pasos con OpenVINO** (rupeshs/SDXL-Lightning-2steps-openvino-int8, revisión fija 347b21e571d7b8a716af83f64d68c5c028c51c56) generó dos 512×896 en 14.79 y 12.40 s, memoria máxima ~11,262,196 KiB. Run **44861295384** SUCCESS. **Calidad cinematográfica NO inspeccionada ni aprobada.**
- scripts/umbral3_lightning_scenes.py genera seis PNG por storyboard, valida formato/no duplicación evidente, registra manifiesto con SHA y civil slot. No considera suficiente una puntuación técnica para aprobar calidad.
- render.render_story_media(... prepared_images=...) permite reutilizar seis PNG verificados; evita repetir difusión al numerar. scripts/umbral3_finalize_from_reserve.py recalcula número oficial de recibos en el día, vuelve a construir intro, voz y portada, bloquea recibos ya publicados y bloquea uso real si visual_approved no es True.
- Tests de recuperación, colisión, daño de imágenes, rechazo de número obsoleto y falsa autorización pasan en las últimas CI. Runs 44862432635 y 44862432628: 160 tests, success.
- Se detectó fallo de regex en una ejecución del motor anterior de candidatos (run **44861417880**): generó el vídeo privado completo pero falló al validar nombre antes de guardarlo. Corrección commiteada y regresión verificada en tests. Este fallo no afectó producción ni Meta.

## Tanda experimental de 14 candidatos

- Las 14 historias civiles 21-27 noviembre están en main e integration. No hay aún 14 vídeos definitivos.
- Workflow `.github/workflows/umbral3_hf_storage.yml` contiene jobs separados `lightning-smoke`, `lightning-batch` y `candidate-inventory` (este último añadido después del primer lanzamiento).
- **Run 44862349621** se disparó con commit `e8bb6e09c255c568610346d54ab61485043c9821` y prefijo `UMBRAL lightning private full`. Primero un Reel índice 0 (smoke) y solo si pasa se generan los otros 13 en matriz con max-parallel 2. Sin Meta tokens. Esta ejecución fue lanzada ANTES de la incorporación de `candidate-inventory`: se requiere auditoría adicional con la versión nueva si los 14 terminan.
- Una ejecución antigua separada de smoke `44861719494` fue cancelada por la cola de concurrencia y sustituida por el full run. No confundir con éxito o fallo audiovisual.
- Este checkpoint **NO afirma** que la tanda haya finalizado o que los vídeos sean aptos para publicar.

## Riesgos y acciones pendientes

1. Ver estado/logs de run 44862349621. Corregir errores en rama si existe fallo y revalidar al menos smoke antes de reejecutar matriz; no inventar resultados.
2. Ejecutar una auditoría OIDC desde runner independiente para los 14 archivos y sus índices, con verificación de media v2 y hashes por escena.
3. Inspeccionar fotogramas de los 14 contactos/portadas y tres Reels completos por acceso autorizado al bucket privado. No usar métricas CLIP como sustituto de revisión visual. Revisar coherencia de personajes, objetos y acción con la narración.
4. Solo tras aprobación: configurar Trusted Publisher **limitado** para workflows de main mediante acción del titular si es requerida; actualizar el publicador en pasos graduales, manteniendo rollback y bloqueo de duplicados.
5. Automatizar reposición de siete días de guiones y Reels, sin material vencido ni numeración especulativa.
6. Configurar retención con borrado únicamente si hay recibo y otra copia segura, sin limpiar jamás archivos de publicación incierta o pendientes de revisión.
7. Observar siete días completos de publicaciones 09/21 antes de declarar finalización.

**Estado de liberación: PR #18 abierta. Reserva verificadamente lista para publicar = 0/14. No autorizar producción por error.**


## Addendum validado — 21/11/2026, primera prueba Lightning completada

- Run [44862349621](https://github.com/fedry23/umbral-automation/actions/runs/44862349621), job `lightning-smoke` 136718806155, terminó **SUCCESS**. Produjo seis imágenes de la historia civil 2026-11-21 / 09 con tiempos individuales ~8-10 s y las ensambló como Reel completo privado.
- Se subió a `Fedry23/umbral-private` el ZIP 15,702,139 bytes, SHA-256 `249f776afc2d7e3c1dc8cff7b4a57df0ba9fb82a5a64573c8c77f3ebd2f419c4`; reporte `UMBRAL3_PRIVATE_CANDIDATE_STORED` confirma `slot_indexed:true`, `private_previews_verified:true`, `ready_to_publish:false`, `visual_review:not_performed`. Los previews individuales de vídeo, portada y hoja de contacto se almacenan **solo en el bucket privado**. Ninguna publicación Meta.
- Este éxito desbloqueó los otros trece trabajos `lightning-batch (1..13)` de la MISMA ejecución, max-parallel 2; estaban queued/in_progress en la última comprobación. **No afirmar 14/14 sin ver sus conclusiones y leer inventario nuevo.**
- scripts/umbral3_hf_candidate_audit.py y el workflow OIDC incorporan auditoría de los 14 Reels sin publicación ni modelos, activable con commit en `ops/umbral3-storage-kick.txt` cuyo mensaje **empiece exactamente `UMBRAL candidate audit`** cuando la matriz esté terminada. Si los ficheros faltan, mostrar faltantes sin inventar aprobación artística. Esa auditoría requiere workflow en commit posterior al disparo de 44862349621, por lo que no forma parte de su snapshot.
- Nueva reposición móvil D+7: `scripts/umbral3_refill_gate.py` comprueba historia exacta, revisión de modelo pinned, hashes y si ya existe; `.github/workflows/umbral3_hf_storage.yml` contiene job `daily-refill` con dos slots y cron 17:07 UTC, pero **solo se ejecutará en main cuando** `vars.UMBRAL3_RESERVE_ENABLED=='true'` y el propietario autorice OIDC estrictamente para main. Es inactivo por defecto y no publica Meta.
- El Centro de control UMBRAL ahora prepara editorialmente D+7 por ambas franjas después de validar mañana, sin cambiar su cron ni sus funciones de respaldo. La automatización existente `UMBRAL 3 · Desarrollo y validación` se actualizó para revisar los runs nuevos y el checkpoint, conservando 11:00 Europe/Madrid. No se crearon tareas adicionales.
- Se añadió caché de pesos SDXL Lightning para futuras ejecuciones en el workspace de Github (`HF_HOME`). El primer commit de caché 68053de... produjo workflow YAML inválido por usar `runner.temp` en jobs.env; se corrigió con `github.workspace` en 127cfee..., y tests de integración posteriores pasaron. No reutilizar la versión rota.
- Tests posteriores de desarrollo: **165/165** exitosos en el job de regresión 136721281869 de run 44863279371, sin publicar. No atribuir 165/165 a commits posteriores hasta que sus propias ejecuciones terminen.
- Sin inspección visual de los fotogramas del modelo, ningún Reel nuevo está aprobado. Prohibido fusionar PR #18 a main o activar la variable de producción.
