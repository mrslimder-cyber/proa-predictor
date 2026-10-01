"""
reset_database.py

Vacia TODAS las tablas de la base de datos (SQLite local o Postgres/
Supabase, segun tu DATABASE_URL actual). Necesario UNA VEZ al migrar de
Proballers/2basketballbundesliga.de a RealGM como fuente de datos: los
ids de equipo y de partido de RealGM son numeros distintos a los que ya
tenias guardados, asi que si no vacias antes de reingerir, acabas con
equipos "duplicados" (mismo club real, dos ids distintos) y el Elo /
las medias moviles se parten en dos series sin conexion entre si.

Uso:
    python reset_database.py            # pide confirmacion
    python reset_database.py --yes      # sin confirmacion (ej. en CI)

Despues de correr esto, lanza `python pipeline.py` (o
`python -m scraper.ingest`) para reingerir todo desde RealGM de cero.
"""
import sys

from db.database import engine, init_db
from db.models import Base


def main():
    skip_confirm = "--yes" in sys.argv

    if not skip_confirm:
        answer = input(
            "Esto va a BORRAR todas las filas de todas las tablas "
            f"(DATABASE_URL = {engine.url}). Escribe 'si' para continuar: "
        )
        if answer.strip().lower() != "si":
            print("Cancelado, no se ha borrado nada.")
            return

    init_db()  # por si faltara alguna tabla
    # Borra en orden inverso de dependencias (tablas con foreign keys
    # primero) para que funcione también en motores que validan FKs al vuelo.
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())

    print("Base de datos vaciada. Corre `python pipeline.py` para reingerir desde RealGM.")


if __name__ == "__main__":
    main()
