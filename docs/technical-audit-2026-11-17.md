# Auditoría técnica inicial cruzada · 2026-11-17

Alcance: árbol de ambos repositorios, rutas críticas de publicación, generación, staging, pruebas, red y GitHub Actions. Esta revisión **no** equivale a una auditoría exhaustiva de todas las ramas de ejecución ni a una garantía de publicación diaria.

## Correcciones aplicadas
- `scripts/stage_daily_reel.py`: corregido sombreado de variable que convertía el nombre del MP4 en una lista; añadidos límites de tamaño y rechazo de entradas ZIP duplicadas.
- `tests/test_stage_daily_reel.py`: pruebas de regresión de recuperación y ZIP.
- `publish_daily.yml`: omitir instalación de FFmpeg si el runner ya dispone de binarios; evita un `apt-get update` innecesario.
- `scripts/wait_public_video.py`: descartar inmediatamente un recurso Pages con Content-Length diferente antes de descargarlo entero; el SHA256 sigue siendo obligatorio cuando el tamaño coincide.
- JARVIS: `regression.yml` ahora vigila `status_overview.py`, `recovery_advisor.py` e `integration/**`.

## Riesgos abiertos y prioridades
1. **Publicación incierta / deduplicación:** `scripts/publish_daily.py` registra el intento persistente antes de la llamada POST, correctamente para prevenir duplicados. Si la ejecución muere entre registrar el intento y la llamada, queda un bloqueo que requiere conciliación manual. No borrar ni reintentar automáticamente.
2. **Exactitud horaria:** el workflow usa dos cron UTC y espera hasta las 21:00 Europe/Madrid. Los disparos de GitHub Actions no tienen garantía de puntualidad. Medir retrasos reales y avisar ante fallo, sin publicar fuera de ventana.
3. **Rendimiento de Pages:** la comprobación descarga MP4 y JPEG para comparar SHA256; la nueva validación de longitud evita transferencias innecesarias cuando el tamaño difiere. El tiempo de despliegue Pages sigue siendo externo.
4. **Workflow histórico de pruebas:** hay varios workflows cinematográficos y de fechas concretas con permisos de escritura. No activarlos ni eliminarlos sin revisar las dependencias y autorizaciones existentes.
5. **JARVIS:** la automatización web todavía no acredita sesiones autenticadas ni sustitución productiva de TinyFish. Mantenerla aislada de la publicación de Meta hasta validar seguridad y fiabilidad con tareas de solo lectura.
6. **Optimización futura:** medir tiempos por etapa (render, artifact download, Pages, Meta processing), después reducir el cuello de botella dominante. No afirmar mejoras de velocidad sin medidas comparables.

## Validación
Las comprobaciones CI se ejecutan por push; los resultados de la última tanda deben verificarse en GitHub Actions. No se ha solicitado publicación ni alterado ningún secreto durante esta auditoría.
