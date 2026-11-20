# UMBRAL 3.0 — Estado de continuidad verificado · 20 noviembre 2026

**No declarar proyecto terminado** antes de comprobar la calidad visual, un almacén real de 14 Reels completos y siete días posteriores de observación. Trabajo exclusivamente en GitHub `fedry23/umbral-automation`. No modificar Curio25 ni JARVIS, no comprar servicios, no publicar Reels experimentales ni repetir POST Meta ambiguos.

## Producción y seguridad

- Horarios oficiales invariables: 09:00 y 21:00 Europe/Madrid. Los workflows oficiales siguen en `main`.
- Episodio 14 «La cámara de frío» confirmado el 20/11 a las 15:24:28 Madrid; recibo `docs/published/2026-11-20_09.json`.
- Episodio 15 «La cuerda de regreso» confirmado el 20/11 a las 21:41:51 Madrid; media ID 18124716275471761 y permalink https://www.instagram.com/reel/Df-iX8FvhzX/; recibo `docs/published/2026-11-20.json`. **No republicar.**
- Próximo número 16 validado en CI del 20/11; recalcular de recibos antes de cada publicación.
- PR #20 fusionada a `main`, commit `fd2c7601c7e4aff6c881ba920e3ec34891be2913`: fallback entre artefactos de generación correctos del mismo día; aislada de motor experimental y Meta. Run `44814314633` aprobado (86 tests y render privado).
- PR #22 fusionada a `main`, commit `675fe8bda580f2b1cf6e98fd24cc3039be618339`: doce historias nuevas para 22–27/11 en ambos catálogos; los relatos del día 21 permanecen idénticos. Gate aislado `44819747125`: 86 tests superados.
- PR #23 sincronización hacia integración mediante commit merge de dos padres `9bec748c94d56f90d1f8de9d388a0dac4e918a63`. Comprobado que `main` es ancestro de `integration/umbral-3` (detrás 0 commits). No fusionar PR #18 (draft) hasta aprobar visual, almacenamiento, piloto, integridad, rollback y viabilidad económica.

## Almacenamiento privado ya conectado, pero pendiente del primer Reel completo

- Bucket privado Hugging Face `Fedry23/umbral-private`; Trusted Publisher OIDC limitado **exactamente** a rama `integration/umbral-3` y workflow `umbral3_hf_storage.yml`. No existe todavía autorización de producción para otros workflows.
- Runs `44818097842` y `44818595816`: privacidad verificada, 1 MiB subido/restaurado con SHA256, ZIP de seis imágenes almacenado/restaurado y reutilizado independientemente del número.
- Scripts de backend `scripts/umbral3_hf_storage.py`, `scripts/umbral3_hf_probe.py`, `scripts/umbral3_hf_roundtrip.py`; backend opcional de cola y preparación; cuota conservadora de 5 GB, cuota real de cuenta NO verificada.
- Empaquetado de medio completo implementado en `scripts/umbral3_evidence.py` (MP4, WAV voz/música, 6 imágenes, portada, intro/outro, subtítulos, informe, manifiesto de hashes por archivo); `scripts/umbral3_hf_persist_media.py` guarda y reconcilia vía OIDC con SDK privado en venv independiente; tests `test_umbral3_full_media_archive.py`, `test_umbral3_hf_storage.py`.
- Primer intento real `44819645243` falló con `UnboundLocalError: Path`; corregido commit `0fcf8dcb1e678316efe7d501e1baa8ae723fc7fe` y test de regresión `1111c54d075ce2c32e57e8d038aa2ffb0893ef4f`.
- Nuevo intento real **`44820280376`**: pasó la prueba de autenticación y estaba renderizando un Reel privado completo al último control. Verificar jobs/logs. La evidencia de almacenamiento real **exige** marcador `UMBRAL3_PRIVATE_MEDIA_STORED` y hashes verificados; no basta el control del paquete sintético.
- Runs de integración `44820441200` (134/134 tests pasados, siguiente número oficial 16; render pendiente) y `44820440179` (quality gate aprobado); gate storyboard `44820426282` correcto. Nuevos commits pueden haber desencadenado pruebas adicionales. No repetir ejecutores activos.
- Automatización existente «UMBRAL 3 · Desarrollo y validación» actualizada conservando horario 11:00 diario. Automatizaciones consultadas correctamente mediante `mcp__Automations__peek`; Centro de control y demás horarios intactos.

## Motor visual

- SDXL OpenVINO INT8 en run `44815232445`: dos imágenes 512×896 producidas, 764,74 s y 768,81 s por imagen; pico RSS ~11,5 GB. **No sostenible así para 12 escenas diarias.**
- FLUX.1 Schnell INT8 seguía ejecutándose en el mismo run, comprobar conclusión, latencia y RAM. Ninguna opción se aprueba sin inspección visual de tres Reels privados completos y coste cero verificado. Turbo/SD1.5 no han satisfecho coherencia/calidad.

## Próximos pasos necesarios

1. Consultar conclusión de `44820280376`: resolver automáticamente cualquier fallo, comprobar subida real, descarga y SHA completo. Persistir al menos **tres** Reels privados inspeccionables, sin artefactos experimentales públicos.
2. Consultar `44815232445` (FLUX). Priorizar nuevo motor gratuito de imagen consistente y sostenible; no sustituir producción solo por aprobar un benchmark técnico.
3. Implementar cola de **Reels completos**, no solo imágenes: 14 paquetes fechados, con generación adelantada, portada, voz, música y subtítulos, verificaciones y composición tardía de número oficial. No activar en producción hasta prueba privada de recuperación y OIDC autorizada para cada workflow que lo necesite.
4. Auditar errores de cron/horarios, duplicados y degradación. Mantener idempotencia de Meta y rollback seguro. Desplegar por fases con pruebas y rollback. Observar siete días reales tras desplegar.
5. Conserva este checkpoint actualizado con SHAs, links de runs, resultados reales y bloqueos; no informar de finalización anticipada.

**Reserva editorial 14/14**, **reserva audiovisual comprobada 0/14** al último control. Coste autorizado adicional: 0 €.
