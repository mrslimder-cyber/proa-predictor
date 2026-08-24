"""
Test rápido de conexión a Supabase.
Guarda este archivo dentro de la carpeta proa-predictor (junto a pipeline.py)
y ejecútalo con: python test_connection.py

Tiene un timeout de 10 segundos, así que si se cuelga la red,
va a fallar rápido en vez de dejarte esperando para siempre.
"""
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv()

db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")

if not db_url:
    print("❌ No encontré DATABASE_URL ni SUPABASE_DB_URL en el .env")
    print("   Revisa cómo se llama la variable en tu .env y en tu código (db.py / config.py)")
    sys.exit(1)

# Mostramos la URL pero ocultando la contraseña
safe_url = db_url
if "@" in safe_url:
    prefix, rest = safe_url.split("@", 1)
    if ":" in prefix:
        user_part = prefix.split(":")[0]
        safe_url = f"{user_part}:**@{rest}"

print(f"🔍 Probando conexión a: {safe_url}")
print(f"   Puerto detectado: {'6543 (pooler)' if ':6543' in db_url else '5432 (directo)' if ':5432' in db_url else 'desconocido'}")

start = time.time()
try:
    from sqlalchemy import create_engine, text
    engine = create_engine(db_url, connect_args={"connect_timeout": 10})
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    elapsed = time.time() - start
    print(f"✅ Conexión exitosa en {elapsed:.1f} segundos")
except Exception as e:
    elapsed = time.time() - start
    print(f"❌ Falló después de {elapsed:.1f} segundos")
    print(f"   Error: {type(e)._name_}: {e}")