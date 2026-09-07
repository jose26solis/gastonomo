"""Pruebas de integracion: contra un postgres:16-alpine real, no SQLite.

El criterio para que una prueba viva aca y no en `tests/` a secas: si SQLite
la puede probar igual de bien, no justifica levantar un contenedor. Lo que
sí justifica un Postgres real -y las pruebas de este paquete- es lo que
SQLite no reproduce: `NUMERIC` exacto en aritmética de SQL, `ON DELETE
CASCADE`/`RESTRICT` reales (SQLite los ignora sin `PRAGMA foreign_keys=ON`,
que esta app nunca enciende), el largo de un `VARCHAR`, y el `ROLLBACK` real
de una transacción con varias escrituras pendientes.
"""
