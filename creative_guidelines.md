# UMBRAL · Guía creativa basada en datos

**Estado:** inicial. Aún NO hay muestra suficiente para optimizar por rendimiento.

## Identidad y calidad
- Todo es ficción original. No presentar los relatos inventados como «casos reales», investigaciones ni noticias.
- Español de España, suspense realista, gancho intrigante en los primeros 2 segundos y giro coherente.
- 140–170 palabras por relato, con 6 escenas visuales específicas y conectadas con el texto.
- Narrador masculino natural, voz a velocidad aproximada 1,08, evitando cortes por subtítulos.
- Música tétrica original a volumen bajo, que no compita con las palabras; sonidos ambientales discretos.
- Evitar repetir títulos, localizaciones, premisas y finales de `stories.json` y `stories.archive.json`.
- Títulos sencillos, evocadores, originales; subtítulos legibles para móvil.
- Nunca usar material de terceros protegido por copyright, ni contratar servicios de pago.

## Coherencia narrativa: requisito imprescindible (desde 16/11/2026)
Los Reels anteriores han acumulado elementos extraños sin justificar y giros que no se deducían de lo sucedido. **Desde ahora se prioriza una historia que se entienda a la primera** sobre el número de sustos o imágenes inquietantes.

### Estructura causal obligatoria
1. **Protagonista y situación:** dejar claro quién habla, dónde está y por qué se encuentra allí.
2. **Incidente único:** introducir UNA regla anómala principal (p. ej. un ascensor reemplaza a quien baja). Todo lo sobrenatural deriva de esa misma regla, en vez de acumular máquinas, llaves, notas, espejos y dobles sin relación.
3. **Decisión humana motivada:** explicar por qué el protagonista investiga, abre, entra, llama, huye, etc.; sus decisiones deben ser naturales.
4. **Pistas con utilidad:** sembrar al menos dos detalles que luego sean relevantes. No mostrar objetos misteriosos que nunca vuelvan a aparecer.
5. **Escalada comprensible:** cada acontecimiento debe surgir del anterior. Preservar continuidad espacial (qué puerta está abierta/cerrada, dónde está cada persona, qué sabe el protagonista) y temporal (sin contradicciones).
6. **Remate inevitable pero sorprendente:** final que revela la regla o cambia el significado de una pista anterior; no introducir de golpe una criatura, un objeto o un poder nuevo.
7. **Lectura sin dudas innecesarias:** en 140–170 palabras debe poder resumirse como «alguien quería X; ocurrió Y; hizo Z; descubrió W». Dejar una sola duda inquietante deliberada; evitar tres o cuatro cabos sueltos.

### Checklist de publicación editorial
- Causa y efecto: ¿se entiende por qué sucede cada escena y por qué el personaje actúa así?
- Consistencia: ¿las seis escenas visuales representan acciones concretas del guion, en el MISMO lugar, con iguales rasgos/objetos, y en orden?
- Objetos: ¿cada pista importante tiene función real? Eliminar lo puramente decorativo que confunda.
- Sorpresa: ¿el final se apoya en información anterior y NO en una novedad arbitraria?
- Claridad oral: ¿la narración se comprende escuchándola una sola vez, sin tener que leer subtítulos?
- Evitar clichés vagos como «una voz susurró mi nombre», «mi reflejo se movió solo» o «una nota con mi letra» si no aportan a la causalidad.
- Revisar de verdad el borrador: detectar un salto lógico, corregirlo y volver a comprobar todo el texto antes de actualizar stories.json.

### Introducción y cierre de marca
El motor audiovisual agrega automáticamente **«Historia número N: Título»** con voz grave y un cierre grave propio. Son piezas de marca, NO forman parte de narration y no deben repetirse ni aparecer como un giro adicional. La voz del relato no se altera. Asignar episode_number único, creciente e inmutable, incluso en episodios de prueba públicos. El episodio 6 «La luz del rellano» está reservado para la prueba cinematográfica. Calcular siempre el siguiente número como máximo existente + 1; no renumerar el episodio 5 ya programado.

## Ciclo semanal de mejora
- Analizar métricas **reales** de Reels publicados (vistas, alcance, me gusta, compartidos, guardados).
- Esperar a tener al menos 5 Reels con >48h de publicación; no concluir nada con muestras pequeñas.
- Comparar **tasas normalizadas** por alcance, no solo visualizaciones brutas; registrar número de Reels y rango de fechas.
- Probar solamente **un cambio creativo** a la vez (gancho, duración narrativa o escenas), sin cambiar la publicación automática.
- No inventar cifras ni afirmar causalidad a partir de correlaciones; anotar hipótesis y cuándo revisarlas.
- Mantener las decisiones en este archivo para que el generador de relatos pueda aprovecharlas.
- Priorizar comprensión y calidad de voz por encima de perseguir el algoritmo.

## Resultados e hipótesis contrastadas
Por determinar cuando haya suficientes datos.


## Prompts de imagen: límite práctico
Escribir 35–50 palabras inglesas por escena, empezando por la acción concreta y
el encuadre. Añadir después solo los rasgos de continuidad imprescindibles. No
anteponer un párrafo común largo: el codificador puede recortarlo y perder la
acción. Revisar las imágenes generadas: pasar validación MP4 no demuestra que
los seis dibujos representen correctamente los seis momentos de la historia.
