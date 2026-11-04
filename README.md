# Radar de Mercado · cotizaciones

Este repositorio existe para una sola cosa: **bajar las cotizaciones del
Radar de Mercado de Yaxché Dara y dejarlas en `datos.json`.**

## Por qué

Las tareas programadas de Claude corren en un contenedor que no alcanza
ninguna fuente de precios — Yahoo, CoinGecko, Stooq, Banxico y los
proveedores de divisas devuelven cero. Lo único que sí responde es
GitHub.

Así que la descarga se hace aquí, en los servidores de GitHub, y la
tarea de la nube lee el resultado. Antes esto dependía de que la Mac
estuviera encendida a las 8:47 de la mañana; si estaba dormida o Víctor
estaba de viaje, el radar se quedaba sin actualizar y nadie se enteraba
hasta abrirlo.

## Cómo funciona

| Hora (CDMX) | Qué pasa | Dónde |
|---|---|---|
| 8:10, de lunes a viernes | GitHub baja 15 referencias y 17 criptos y guarda `datos.json` | aquí |
| 8:47, de lunes a viernes | Claude lee `datos.json` y publica el radar | la nube |

La media hora de margen está a propósito: GitHub puede retrasar las
tareas programadas cuando hay mucha carga.

## Qué mirar si algo falla

1. **Pestaña Actions.** Una corrida en rojo dice en qué símbolo falló.
2. **La fecha de `datos.json`.** Si lleva días sin cambiar, la tarea no
   está corriendo.
3. **El radar mismo** enciende un aviso cuando la tabla viene de un
   corte anterior, y la tarea de las 7:36 avisa si pasa de ocho días.

Para dispararla a mano: pestaña **Actions → Radar · cotizaciones → Run
workflow**.

## Reglas que el script respeta

- Si una referencia falla, **se arrastra su último valor bueno con la
  fecha de ese día**, no se inventa ni se borra. Omitirla sin más no
  funciona: el generador del radar rehace la tabla entera con lo que
  recibe, así que un símbolo ausente desaparece de la página sin que
  nadie lo note. Arrastrado, el renglón sigue ahí y su sello delata que
  no es de hoy.
- Si más de un tercio de la tabla hubo que arrastrarla, **no se escribe
  el archivo**: eso ya no es un radar de hoy.
- Si el precio y el último cierre semanal se separan más de 2%, la fila
  se marca con un aviso de desvío en lugar de elegir en silencio.

## Advertencia de GitHub

GitHub apaga las tareas programadas de un repositorio **sin actividad
durante 60 días**. Los commits que hace la propia tarea no siempre
cuentan. Si un día deja de correr sola, entre a Actions y vuelva a
activarla — o haga cualquier cambio en el repositorio cada par de meses.
