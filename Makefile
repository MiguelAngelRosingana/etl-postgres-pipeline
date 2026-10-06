.PHONY: up down init-db demo resumen test test-int lint

up:            ## Levanta PostgreSQL con Docker
	docker compose up -d --wait

down:          ## Para y borra el contenedor y sus datos
	docker compose down -v

init-db:       ## Crea el esquema en una base de datos que ya existe (sin Docker)
	python -m etl init-db

demo:          ## Procesa los dos ficheros de ejemplo
	python -m etl run data/sample/ventas_2026-10-01.csv
	python -m etl run data/sample/ventas_2026-10-02.csv

resumen:       ## Muestra las últimas ejecuciones
	python -m etl resumen

test:          ## Tests unitarios (no necesitan base de datos)
	pytest -m "not integracion"

test-int:      ## Todos los tests; los de integración necesitan TEST_DATABASE_URL
	pytest

lint:
	ruff check .
