# UMBRAL 3.0 — Gates reales de salida · 21 noviembre 2026

Este documento conserva solo hechos comprobados. **NO habilitar la PR #18 ni la publicación de candidatos** mientras falte revisión visual, prueba de OIDC main y lectura Meta en el instante de publicación. No modificar Curio25, JARVIS ni los horarios oficiales (09:00/21:00 Europe/Madrid).

## Producción y número oficial
- `docs/published/2026-11-21_09.json`: episodio **16**, «La pintura fresca», Instagram media `18137894143763489`, publicado 09:00 Madrid y comprobado mediante lectura Meta.
- Producción `main` NO publica los candidatos experimentales. `main` ya contiene PR #20 y #22, más la PR #25 que es **solo la prueba OIDC**. No hay activación visual.
- La prueba real del 22/11 por la mañana [44907218395](https://github.com/fedry23/umbral-automation/actions/runs/44907218395) restauró seis escenas e hizo un MP4 privado, pero arrojó el número **16** usando recibos de integración obsoletos. Esto es un defecto de asignación, no una autorización de producción.
- Corrección en `scripts/umbral3_finalize_from_reserve.py`: `official_receipts_root` desacopla historias de desarrollo de recibos oficiales actualizados; añade prueba para rechazar numeración obsoleta, y un job que obtiene `main` con `actions/checkout@v4`. La repetición [44907865366](https://github.com/fedry23/umbral-automation/actions/runs/44907865366) debe examinarse antes de afirmar que está resuelto. **Un checkout de main no sustituye la reconciliación Meta inmediatamente antes del POST oficial.**

## HF OIDC production, bloqueo humano conocido
- PR [#25](https://github.com/fedry23/umbral-automation/pull/25) **fusionada** en `main` SHA `78ef999dd3ca6a36f512865e869ba6227f9d29ec`, tras 88/88 pruebas. Añade el único job `production-oidc-probe` a `.github/workflows/umbral3_hf_storage.yml`: exclusivamente `main`, `contents:read`, `id-token:write`, sin Meta, sin render y sin cron.
- Prueba `main` [44907590484](https://github.com/fedry23/umbral-automation/actions/runs/44907590484) FAILED exclusivamente en el intercambio OIDC: `OIDC exchange failed; check trusted publisher claims`. El publisher existente en Hugging Face solo cubre la rama `integration/umbral-3`.
- Acción necesaria del propietario en bucket `Fedry23/umbral-private` → Settings → Trusted Publishers → Add: proveedor GitHub Actions, repositorio `fedry23/umbral-automation`, rama `main`, archivo `umbral3_hf_storage.yml`, read-only desactivado para la futura escritura del D+7. **No borrar ni ampliar el publisher restringido de desarrollo**. Tras guardarlo, repetir prueba main sin acceso Meta.
- La rama de integración incorpora ya el mismo job `production-oidc-probe` en su workflow completo, con `daily-refill` condicionado a `vars.UMBRAL3_RESERVE_ENABLED=='true'`.

## Reserva, datos y revisión audiovisual real
- [44891884792](https://github.com/fedry23/umbral-automation/actions/runs/44891884792) comprobó `stored_complete=14`, `missing=[]`, `corrupt=[]`, `ready_reels=0`, `visual_approved=0`, `total_bytes=238507865` para los catorce candidatos fechados **21–27/11**. **NO equivale a 14 huecos futuros**: el del 21/11 a las 09:00 ya está consumido oficialmente; la reposición D+7 requiere historias adicionales del 28/11.
- Para inspección humana, [44907692744](https://github.com/fedry23/umbral-automation/actions/runs/44907692744) produjo un solo JPEG `2664×3032` con las **84 escenas**, a partir de los 14 ZIP verificados y sus SHA, conservado únicamente en la zona privada `umbral3/private-review/_boards/`. Hash del panel: `b0c3dce9db310a2882dd15905017a961db26921ff5b5da80ac3a71a017e323e2`. No publicar este JPEG ni adjuntarlo a GitHub Actions público; el propietario puede descargarlo de su bucket privado y compartirlo directamente en chat para revisión.
- El procedimiento `scripts/umbral3_visual_approval.py` impide aprobar el material cambiando simplemente una marca local. Solo admite un registro propietario por fecha/slot, ligado a SHA-256 de la historia y seis PNG exactos, con revisor y fecha. **Aún no hay ninguna revisión humana realizada** y no deben generarse aprobaciones falsas.
- SDXL Lightning: benchmark [44861295384](https://github.com/fedry23/umbral-automation/actions/runs/44861295384) ~12–15 s/fotograma en CPU. Ningún benchmark confirma coherencia visual cinematográfica.

## Reposición D+7 y horarios
- El cron anterior `07 17 * * *` caía a las 18:07 CET, **antes de la preparación editorial de las 18:20**. Cambiado en desarrollo a `42 20 * * *` → 21:42 CET / 22:42 CEST, después de la publicación oficial 21:00 y del respaldo 21:20. Pruebas de ambos cambios DST añadidas.
- La reposición automática sigue desactivada por defecto: requiere main OIDC, historias D+7, aprobación visual, pruebas correctas y activación controlada de la variable. No habilitarla mientras existan candidatos sin revisar.

## Estado GitHub y pruebas
- Se fusionó `main` hacia `integration/umbral-3` usando dos padres y copiando el recibo y material publicado del 21/11: commit `8cc7def1f89e2b9f3c06f65d7b2e6fc76a0b8876`. Comparación inmediatamente posterior: desarrollo `behind=0` y producción permanece intacta; revalidar HEAD si hay nuevas automatizaciones.
- Al menos **175 pruebas** superadas en [44907780544](https://github.com/fedry23/umbral-automation/actions/runs/44907780544); pruebas añadidas posteriores y rama actual deben volver a validarse. No contar una prueba `in_progress` como completada.
- PR #18 permanece sin fusionar por seguridad.

## Condiciones de cierre que NO están verificadas
1. Inspección humana de los 14 Reels y sus fotogramas; escenas malas regeneradas y aprobaciones reales basadas en hashes.
2. OIDC main nuevo, probado y con mínimo privilegio.
3. Reconciliación Meta del número oficial con lock inmediatamente antes de POST; evitar duplicados y estados inciertos.
4. Reposición D+7 que no consuma historias inexistentes ni candidatos caducados; prueba con un hueco real y rollback.
5. PR #18 con gates end-to-end aprobados y fusión segura; siete días consecutivos reales observados.

No declarar finalización hasta lograr estos puntos, aunque el almacenamiento y los 14 ZIPs estén íntegros.
