# TSP: algoritmo genético y programación entera

Proyecto de Modelación y Simulación. Requiere Python 3.10 o superior.

## Ejecución

Desde esta carpeta, crear y activar un entorno virtual si se desea. Luego:

```bash
python -m pip install -r requirements.txt
python main.py ejecutar --escenario demo
python main.py comparar
```

`comparar` ejecuta eil101, gr229 y el escenario propio. Cada ejecución crea una
carpeta nueva dentro de `resultados/`. Para ver todas las opciones:

```bash
python main.py ejecutar --help
```

Se fija PuLP 3.3.0 porque PuLP 4 cambia su API. Si CBC no está incluido para su
plataforma, será necesario instalarlo; el programa comprueba su disponibilidad.
El GA puede ejecutarse sin PuLP con `--metodo ga`.

## Organización

| Archivo | Responsabilidad |
| --- | --- |
| `main.py` | Comandos y argumentos |
| `rutas/datos.py` | Lectura, descarga, generación y distancias |
| `rutas/recorridos.py` | Validación y heurísticas de rutas |
| `rutas/genetico.py` | Población, selección, cruce y mutación |
| `rutas/lineal.py` | Modelo entero DFJ con PuLP/CBC |
| `rutas/experimentos.py` | Repeticiones, estadísticas y exportación |
| `rutas/graficas.py` | Rutas, convergencia y animación |
| `tests/` | Pruebas con unittest |

El paquete se ejecuta directamente, sin instalar el proyecto, herencia o capas
de servicios. Las únicas clases de datos son la instancia y la configuración GA.

## Escenarios incluidos

| Nombre | Ciudades | Distancia | Óptimo publicado |
| --- | ---: | --- | ---: |
| `demo` | 10 | Euclidiana real | Se obtiene con el modelo |
| `eil101` | 101 | EUC_2D | 629 |
| `gr229` | 229 | GEO | 134602 |
| `propio` | 80 | EUC_2D | Se obtiene con el modelo |

El escenario propio representa cuatro barrios ficticios de 20 ciudades cada uno.
No son coordenadas reales ni distancias por carretera. Para regenerarlo:

```bash
python main.py generar --ciudades 80 --semilla 2026 --reemplazar
python main.py descargar
```

El segundo comando recupera instancias oficiales ausentes desde Heidelberg o
Rice. Las copias se verifican por nombre, dimensión, métrica y huella de sus
coordenadas. El lector acepta TSPLIB TSP con NODE_COORD_SECTION y tipos EUC_2D/GEO,
y CSV con columnas `ciudad,x,y` y distancia real. Rechaza otros formatos.

## Algoritmo genético

```bash
python main.py ejecutar --escenario eil101 --metodo ga --poblacion 200 --iteraciones 800 --seleccion mezcla --sobrevivientes 0.10 --cruce 0.70 --mutacion 0.20 --semillas 11 22 33 44 55
```

- Cromosoma: permutación de todas las ciudades. La distancia incluye el regreso.
- Selección: torneo, ranking lineal, padres de la élite o mezcla torneo/ranking 50/50.
- Cruce OX y mutación por inversión. Las tres fracciones suman 1 y determinan
  cuántos individuos sobreviven, se cruzan o mutan. El redondeo va a mutación.
- Se conservan los mejores como sobrevivientes. Los clones fuera de la élite se
  sustituyen con inmigrantes aleatorios; se mide diversidad por rutas únicas,
  considerando equivalentes sus rotaciones e inversiones.
- Inicialización mixta: 20 % vecino cercano con inicio aleatorio y resto
  aleatorio. `--inicializacion aleatoria` desactiva la parte heurística.
- Se minimiza distancia directamente, equivalente a maximizar `1/(1+D)`.
- `--mejora-local 2` permite hasta dos cambios 2-opt por hijo. Esta variante se
  identifica como `GA+2opt`. Por defecto la mejora está desactivada.

Se guardan las tres mejores rutas distintas encontradas durante toda la evolución.
Se hacen cinco repeticiones por defecto. La animación muestrea la evolución e
incluye las generaciones inicial y final.

## Programación entera

El modelo DFJ usa una variable binaria por arista no dirigida, con `i < j`:

```text
minimizar sum(d[i,j] * x[i,j])
sujeto a sum(x incidentes a i) = 2                  para cada ciudad i
         sum(x[i,j] con i,j en S) <= |S|-1          para cada subruta S
         x[i,j] en {0,1}
```

Las restricciones de subrutas se añaden al encontrar ciclos separados. Un
recorrido único obtenido de un subproblema resuelto a optimalidad demuestra el
óptimo TSP. Se revisan los estados de problema y solución de PuLP conjuntamente.
La etiqueta LP de los resultados corresponde a este modelo entero.

Hay `n(n-1)/2` variables y se empieza con `n` restricciones de grado. La tabla
cuenta las restricciones realmente agregadas. Cada resolución recibe el tiempo
restante del límite global, de 120 segundos por defecto. La preparación y las
tolerancias del solver pueden causar una pequeña diferencia con ese límite.

El inicio factible usa vecino cercano y 2-opt independientemente del GA. Si el
solver no devuelve un recorrido mejor, se conserva ese inicio y se informa
`origen=inicio_factible`; una ruta del solver indica `origen=solver`. El inicio
no demuestra optimalidad. No se usan recorridos óptimos publicados al resolver.

```bash
python main.py ejecutar --escenario gr229 --metodo lp --limite-lp 600
```

No se garantiza demostrar los óptimos grandes dentro de un límite corto. Se
registran ruta, cota inferior, brecha, origen y estado. Los óptimos publicados
solo se usan como referencia de comparación.

## Salidas y pruebas

Se exportan CSV de comparación, repeticiones, estadísticas y rutas; JSON con
parámetros e historia; gráficas PNG y una animación GIF. La subcarpeta `lp/`
contiene el modelo y los logs. `comparacion_total.csv` reúne todos los escenarios.
Las rutas CSV usan identificadores originales e incluyen el regreso al origen;
las rutas internas JSON son índices desde cero.

La tabla compara LP y las tres mejores rutas GA distintas, con ciudades, población,
generaciones, variables, restricciones, tiempo, distancia y porcentaje de error:

```text
error (%) = 100 * (distancia - óptimo) / óptimo
```

La referencia de eil101/gr229 es TSPLIB. Para otros casos se usa el óptimo probado
por LP; si no se demuestra, óptimo y error quedan vacíos. La brecha del solver se
calcula contra su cota inferior y es diferente del error contra TSPLIB. El tiempo
GA corresponde a toda la corrida que encontró la ruta. Gráficas y exportaciones
quedan fuera de los tiempos de los algoritmos.

```bash
python main.py comparar --metodo ga --sin-animacion
python main.py ejecutar --escenario demo --metodo ga --sin-graficas --sin-animacion
python -m unittest discover -s tests -v
```

Las pruebas LP se omiten si faltan PuLP/CBC. El recorrido óptimo en `tests/fixtures/`
se usa únicamente para validar distancias, nunca como entrada a los algoritmos.

## Referencias de implementación

- [Paquetes Python](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/).
- [Distancias TSPLIB](https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/TSPFAQ.html).
- [Óptimos publicados](https://comopt.ifi.uni-heidelberg.de/software/TSPLIB95/tsp/TSP-BEST.html).
- [DFJ y eliminación de subrutas](https://scipbook.readthedocs.io/en/latest/routing.html).
- [Cambios de PuLP](https://www.coin-or.org/pulp/guides/how_to_migrate_to_v4.html).
- [Copia eil101](https://github.com/coin-or/jorlib/blob/master/jorlib-core/src/test/resources/tspLib/tsp/eil101.tsp).
- [Copia gr229](https://static.tspsolver.com/tsplib/gr229.tsp).
- [Recorrido de prueba eil101](https://nojhan.net/git/nojhan/paradiseo/commit/1100fbdb90b458e7efe71c0a02ecd10c5f09c49a).
