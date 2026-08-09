"""
Diagnóstico: por qué el split temporal de entrenamiento tiene una sola clase.

Colócalo en la raíz de proa-predictor (junto a pipeline.py) y ejecútalo con:
    python diagnose_home_win_balance.py
"""
from config import TEST_SIZE_FRACTION
from features.feature_engineering import build_dataset

df = build_dataset().sort_values("date").reset_index(drop=True)
print(f"Total de partidos utilizables: {len(df)}")
print(f"Rango de fechas: {df['date'].min()} -> {df['date'].max()}")
print(f"Valores nulos en 'date': {df['date'].isna().sum()}")
print(f"Fechas duplicadas: {df['date'].duplicated().sum()}")

split_idx = int(len(df) * (1 - TEST_SIZE_FRACTION))
train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]

print("\n--- Distribución global de home_win ---")
print(df["home_win"].value_counts())

print("\n--- Distribución en TRAIN (split temporal actual) ---")
print(train_df["home_win"].value_counts())
print(f"Fechas del train: {train_df['date'].min()} -> {train_df['date'].max()}")

print("\n--- Distribución en TEST ---")
print(test_df["home_win"].value_counts())

# Buscamos en qué punto (si existe) aparece la primera derrota local,
# para saber cuánto del dataset está "contaminado" con solo victorias locales.
first_away_win_idx = df.index[df["home_win"] == 0]
if len(first_away_win_idx) == 0:
    print("\n[ALERTA] No hay NINGUNA derrota local en TODO el dataset. "
          "Esto es un problema de datos (home_score/away_score), no del split.")
else:
    idx0 = first_away_win_idx[0]
    print(f"\nLa primera derrota local (home_win=0) aparece en la fila {idx0} "
          f"de {len(df)} (fecha {df.loc[idx0, 'date']}).")
    print(f"Eso es el {idx0 / len(df):.1%} del dataset. "
          f"Tu split de train usa el primer {1 - TEST_SIZE_FRACTION:.0%}.")

# Evolución por bloques de 100 partidos, para ver si el desbalance es
# progresivo (liga rara al principio) o total (bug de datos).
print("\n--- % de victorias locales por bloques de 100 partidos (orden cronológico) ---")
block = 100
for start in range(0, len(df), block):
    chunk = df.iloc[start:start + block]
    print(f"  filas {start:4d}-{start + len(chunk):4d}: "
          f"{chunk['home_win'].mean():.1%} victorias locales "
          f"({chunk['date'].min()} -> {chunk['date'].max()})")
