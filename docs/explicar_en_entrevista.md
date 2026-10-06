# Cómo explicar este proyecto en una entrevista

## En 60 segundos

"Es un pipeline ETL en Python que carga ficheros de ventas en PostgreSQL. Lee el CSV todo como
texto, valida y normaliza cada fila, aparta las inválidas con su motivo, y carga las buenas en una
tabla de staging y de ahí, con un upsert, al modelo definitivo. Lo diseñé para que sea
idempotente: puedes ejecutarlo dos veces sobre el mismo fichero y no duplica nada, y si falla a
mitad, la transacción se deshace y la ejecución queda registrada como error. Tiene tests
unitarios y de integración contra un PostgreSQL real, y CI en GitHub Actions."

## Preguntas que puede hacer el entrevistador

**¿Cómo evitas duplicados?**
Con `INSERT … ON CONFLICT (id_venta) DO UPDATE`, con deduplicación por `id_venta` antes de
cargar (gana la última línea del fichero) y con la huella SHA-256 del fichero para no procesar dos
veces el mismo.

**¿Qué pasa si falla a mitad de la carga?**
Staging, clientes, ventas, filas rechazadas y el cierre de la ejecución están en una sola
transacción: se deshace todo. El error se registra en `etl.ejecuciones` en otra transacción.
Hay un test que fuerza el fallo y comprueba que no queda nada cargado.

**¿Cómo garantizas la calidad de los datos?**
Nueve reglas de validación (id, fecha, fecha futura, email, nombre, producto, cantidad, precio,
estado). Cada fila rechazada se guarda con su línea, su motivo y la fila original, y se comprueba
que leídas = válidas + rechazadas + duplicadas.

**¿Por qué una tabla de staging?**
Para separar la carga de la integración: primero aterrizan los datos validados y después, con SQL
basado en conjuntos, se integran. Es `UNLOGGED` porque se vuelve a llenar en cada ejecución.

**¿Por qué `IS DISTINCT FROM` en el upsert?**
Para no reescribir filas que no han cambiado. Así `actualizadas` cuenta solo cambios reales y se
evitan escrituras inútiles.

**¿Cómo sabes cuántas filas insertaste y cuántas actualizaste?**
Con `RETURNING (xmax = 0)`, que es verdadero en las insertadas. Es una técnica conocida de
PostgreSQL, aunque se apoya en un detalle de implementación.

**¿Qué mejorarías?**
Carga incremental con marca de agua contra una fuente viva, gestión de borrados del origen,
orquestación con Airflow y mover las transformaciones a dbt.

**¿Qué relaciones hay entre las tablas?**
`ventas` apunta a `clientes` (uno a muchos) con `ON DELETE RESTRICT`, así que no se puede borrar un
cliente con ventas. Hay un test que lo comprueba. `filas_rechazadas` apunta a `ejecuciones`. Las
claves foráneas están indexadas.

## Qué no decir

No digas que el proyecto "está en producción" ni que procesa datos reales: son datos sintéticos.
Lo que sí puedes decir es que está probado contra un PostgreSQL real y que lo ejecutas con Docker.
