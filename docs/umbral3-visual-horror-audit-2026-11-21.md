# UMBRAL 3 — revisión visual de terror (21-11-2026)

**Material:** panel privado de 84 imágenes para 14 relatos (21–27/11/2026), facilitado por el propietario en el chat. Se comparó con los guiones y las acciones del storyboard de la rama `integration/umbral-3`. Esta evaluación valora los fotogramas estáticos del panel; **no es** una inspección temporal ni sonora de los MP4.

**Dictamen de esta ronda:** `visual_approved=0`, `ready_reels=0`. La mejora de nitidez/composición es evidente, pero la mayoría de imágenes se leen como fotografía publicitaria, documental o thriller sin anomalía sobrenatural. No crear certificados ficticios de revisión del propietario. No publicar candidatos.

## Hallazgos verificables en el panel

| Fecha/slot | Episodio | Problema principal que debe corregir el nuevo arte |
|---|---|---|
| 21/09 | La pintura fresca | Sala muy iluminada y cotidiana; la forma humana bajo el yeso no construye amenaza, el hombro imposible final no destaca |
| 21/21 | El último doblaje | Estudio musical cálido y acogedor; ni el bucle de la cinta ni la parálisis se leen en las imágenes |
| 22/09 | El ascensor de servicio | Escenario de oficinas normal; traje del trabajador no consistente y transformación de edad, alianza y planta desalineada poco perceptibles |
| 22/21 | El banco de la parada | Parada aparentemente diurna y corriente; falta la versión sumergida, autobús con pasajeros atrapados y reflejo imposible |
| 23/09 | El carrete sin revelar | Decoración doméstica normal; las fotos que deberían representar puntos de vista ocultos apenas se distinguen y falta la imagen desde la boca |
| 23/21 | El paquete sin remitente | Caja y habitaciones normales; faltan objetos imposiblemente trasladados y la ausencia física de la cerradura |
| 24/09 | El grifo del patio | Grifo/patio corrientes; el agua que asciende y la deshidratación imposible del padre no son claras |
| 24/21 | La última página | Museo y mobiliario decorativos; falta la rotura sin causante, la desaparición de la salida y las letras autónomas |
| 25/09 | El plano del desván | Dormitorio y desván convencionales; no se aprecia que el dibujo altere la arquitectura ni las múltiples puertas imposibles |
| 25/21 | El taxi de la otra acera | Cohesión espacial débil, objetos/coche diferentes; faltan el taxímetro anómalo y la puerta doméstica que conduce al taxi |
| 26/09 | El botón verde | Relojes/vestuarios genéricos; se confunde la máquina de fichar con otra maquinaria, la desaparición del compañero no se narra |
| 26/21 | La radio del sótano | Distintas radios y escenas limpias; falta la amenaza que se aproxima con el dial y los golpes desde el armario |
| 27/09 | Las huellas de sal | Las huellas parecen oscuras o rojizas más que cristales blancos; no se percibe que aparezcan solas ni los pasos gigantes |
| 27/21 | El abrigo de la consigna | Fotografía de moda/noir; el abrigo, la llave y la figura que reclama la prenda carecen de tensión sobrenatural |

## Intervención en código, aislada de producción

- `scripts/umbral3_horror_direction.py`: **84 acciones sobrenaturales concretas**, seis por relato; crescendo visual, luz y composición de terror. Impide por diseño sustituirlas por adjetivos genéricos.
- `scripts/umbral3_lightning_scenes.py`: `UMBRAL_HORROR_DIRECTION=horror-v2` opt-in; prompts con límite real del tokenizador CLIP; semillas nuevas; backend de almacenamiento **distinto** `sdxl-lightning-2steps-ov-int8-horror-v2` para no sobrescribir los 14 candidatos anteriores.
- `tests/test_umbral3_horror_direction.py`: cobertura para 14 relatos, 84 beats, no mutación editorial y error cerrado si el modelo no puede recibir el prompt.
- Job `horror-direction-smoke` dentro del workflow OIDC autorizado, sin permisos Meta; muestra el caso crítico `El banco de la parada` (22/11 21h) como **preview privado no aprobado**.

**Gates de aprobación pendientes:** comparar panel antiguo/nuevo sin ocultar escenas erróneas; verificar anomalías inequívocas que sucedan donde dicta la narración, misma identidad/escenario en planos relacionados, exposición que permita entender la acción, cinematografía de miedo y sincronía de escenas/audio. Mantener `visual_approved=false` y `ready_to_publish=false` hasta revisión real del propietario. No mover `main`, no activar reposición D+7 ni PR #18 por estos cambios experimentales.


## Revisión adicional del propietario — 22/11 21h, El banco de la parada (horror-v2)

El propietario adjuntó el panel **real** de seis escenas de `horror-v2` el 21/11/2026. El panel se leyó visualmente y se cotejó con la narración del repositorio. Resultado: **rechazado para publicar; mejora de atmósfera pero insuficiente fidelidad de la acción**.

1. Parada: ambiente de niebla y verde apagado; funciona como localización, falta el charco inquietante bajo el asiento.
2. Reflejo: parada y reflejo legibles, pero no se ve una parada **sumergida** en su reflejo.
3. Agua: formas negras que parecen objetos o barcas; no se reconocen zapatos y piernas siendo engullidos.
4. Huida: escena paisajística mojada y reflejo de árbol; no hay huellas humanas húmedas inequívocas.
5. Autobús: dos figuras en una puerta o umbral, **no** pasajeros golpeando el cristal de un autobús.
6. Paradoja final: un hombre sentado de verdad y reflejado con normalidad; la historia requiere **banco vacío en realidad y hombre sentado solo en el agua reflejada**.

**Corrección implementada:** `scripts/umbral3_horror_v3.py`, prompts cortos centrados primero en el hecho sobrenatural; `UMBRAL_HORROR_DIRECTION=horror-v3` con semillas y backend distintos para evitar sobrescritura; nuevo job `horror-v3-smoke` en workflow privado y test `tests/test_umbral3_horror_v3.py`. La producción `main`, el publicador y los catorce candidatos anteriores permanecen intactos. Revisar visualmente el nuevo contacto antes de aprobación; un pipeline verde no equivale a terror aprobado.

Prueba privada V3: https://github.com/fedry23/umbral-automation/actions/runs/44916727088 (resultado sujeto a comprobación posterior).
