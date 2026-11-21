# UMBRAL 3.0 · checkpoint verificable de despliegue · 2026-11-21

## Alcance y reglas irrevocables

- Proyecto exclusivo: `fedry23/umbral-automation`. No modificar Curio25 ni JARVIS.
- `main` continúa operando 09:00 y 21:00 Europe/Madrid. No hay publicación experimental, ni cambio de token, ni gasto contratado.
- La aprobación del propietario cubre EXACTAMENTE el panel mixto V3/V3.1 SHA-256 `859be1ef1001f5be6476c87db5c90a47f866a30b19d91a39597bbea748e14b2e`: 14 relatos y 84 PNG concretos, NO nuevas imágenes, NO autoriza automáticamente MP4/Meta.
- No activar ni fusionar `PR #18` hasta completar una salida reversible y sus controles. No prometer siete días de observación sin que transcurran.

## Evidencia real confirmada

1. Fusión segura de última producción `fd940277f9817bf8757b9940e9564c2aa6511fe6` hacia integración `0250d2f2a9dad6d285ef404ad3fca5b76e730221`, preservando voz y recibos; tras esto la comparación de ramas indica `behind_by=0` (revalidar al continuar).
2. `scripts/umbral3_release_policy.py` y `scripts/umbral3_approved_restore.py`: selección por fecha/turno, SHA de historia, paquete privado, panel aprobado y cada uno de seis PNG. Los archivos originales permanecen inmutables. Falla cerrada en intentos inciertos o medios alterados.
3. GitHub Actions private smoke SUCCESS `44946361325`: OIDC, seis PNG V3.1 auténticos y aprobados, MP4 real de 4.836.290 bytes, episodio tardío 18 para `2026-11-22 09`, decodificación WAV/music/MP4, subtítulos y portada; `private_test=true`, cero POST a Meta.
4. Nueva ruta de preparación `scripts/umbral3_live_stage.py`; nuevo job principal `live-owner-approved-release` en el workflow de storage OIDC, con bloqueo `umbral-instagram-official`, staging, Meta preflight y lectura oficial posterior. No se encuentra en `main`.
5. El nuevo job está **desactivado por defecto** y requiere `vars.UMBRAL3_LIVE_ENABLED == 'v31-owner-reviewed-859be1ef'` y `vars.UMBRAL_META_PUBLISH_ENABLED != 'false'`. La versión anterior conserva ventanas de recuperación. La variable jamás se ha activado aquí.
6. En los commits de integración `37001546265e5a7505a4afab8384f5e2f9a82981` y `d1d18d4c6e2864a1c42ba136ee03c9fb9b6cc751` el conjunto CI superó **227/227** pruebas de calidad/integración; verificar de nuevo las ejecuciones posteriores. `scripts/episode_state` mantiene el último episodio oficial 17 y ninguna intención pendiente no resuelta.
7. Auditoría HF privada real `44947563100`: el 28 Nov 09 y 21 tienen guiones pero `generate=true`, `generated=false`, no están guardados; el informe de próximas 14 franjas marca 12 aprobadas y 2 faltantes. No existe una reserva continua de 14 medios aprobados.
8. Segunda prueba privada `44947175216` detectó error EN LA ASERCIÓN del salto de línea de caption, aunque el MP4 decodificó correctamente. Corrección `1c88107578904d4b7e465f103a344ebfc8f086fa`; nuevo job de prueba privada `44947626821` solicitado. Consultar su conclusión, y no afirmar PASS si está inacabado.

## Bloqueos reales pendientes

- Confirmar PASS de la prueba privada reforzada `44947626821`, incluidas portada, duración, metadatos y caption del stage oficial.
- Probar la ruta principal con una ejecución oficial real programada **sin pruebas Meta ficticias** y verificar su permalink/recibo en Meta. Antes de activarla, asegurar rollback real y diferenciar fallo del modelo de fallo de la red.
- Mantener la PR #18 draft hasta comprobar identidad main OIDC, contratos staging/Meta y rollback, y verificar que el interruptor no salta las medidas de seguridad. No fusionar 200+ commits sin revisión.
- Generar **nuevos** medios para el 28 Nov y guiones desde el 29 Nov en adelante. Sus nuevas escenas **requieren revisión explícita**, por voluntad del propietario; no autoconceder aprobación.
- Demostrar funcionamiento estable durante siete días reales después de la salida, sin presumirlo anticipadamente.
- Los 14 candidatos 21–27 Nov incluyen dos slots del 21 que ya se publicaron: no reutilizar ninguna publicación ni un número provisional.

## Continuar de forma segura

1. Comprobar HEAD actual y todos los runs de CI/privados (incluyendo `44947626821`).
2. Si un test falla, obtener logs precisos, corregir y repetir. No usar `green` por mera ausencia de un fallo anunciado.
3. Revalidar fecha/hora local y estado de Meta antes de habilitar cualquier cambio de producción.
4. Mantener el switch OFF y las tareas antiguas intactas hasta que exista prueba real de reserva/editorial/reversión; registrar checkpoints verificables en PR #18.
