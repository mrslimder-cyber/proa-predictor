"""
Entrena dos modelos con XGBoost:
1. Clasificador -> probabilidad de victoria del equipo local
2. Regresor -> margen de puntos esperado (local - visitante)

Por qué split TEMPORAL y no aleatorio:
En deportes, un split aleatorio 80/20 deja que el modelo "vea" partidos
de marzo para predecir partidos de enero, lo cual es información del
futuro. Usamos los primeros partidos de la temporada para entrenar y
los últimos para validar, simulando cómo se usaría el modelo en la
realidad (predecir la jornada siguiente con lo que se sabe hasta hoy).

Uso:
    python -m models.train_model
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, mean_absolute_error
from xgboost import XGBClassifier, XGBRegressor

from config import MODELS_DIR, MODEL_VERSION, TEST_SIZE_FRACTION, RANDOM_STATE
from features.feature_engineering import build_dataset

NON_FEATURE_COLS = {"game_id", "date", "home_win", "margin"}


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in NON_FEATURE_COLS]


def temporal_split(df: pd.DataFrame, test_fraction: float):
    df = df.sort_values("date").reset_index(drop=True)
    split_idx = int(len(df) * (1 - test_fraction))
    return df.iloc[:split_idx], df.iloc[split_idx:]


def train():
    df = build_dataset()
    print(f"Dataset construido: {len(df)} partidos utilizables.")

    if len(df) < 50:
        print(
            "[AVISO] Muy pocos partidos disponibles todavía para entrenar algo "
            "fiable. Sigue ingiriendo jornadas y vuelve a entrenar más adelante. "
            "Se entrenará igualmente para dejar el pipeline probado de extremo a extremo."
        )

    train_df, test_df = temporal_split(df, TEST_SIZE_FRACTION)
    feature_cols = get_feature_columns(df)

    X_train, y_train_cls = train_df[feature_cols], train_df["home_win"]
    X_test, y_test_cls = test_df[feature_cols], test_df["home_win"]
    y_train_reg, y_test_reg = train_df["margin"], test_df["margin"]

    # --- Clasificador de victoria ---
    clf = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
    )
    clf.fit(X_train, y_train_cls)

    # --- Regresor de margen de puntos ---
    reg = XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=RANDOM_STATE,
    )
    reg.fit(X_train, y_train_reg)

    # --- Evaluación honesta (solo sobre los últimos partidos, nunca vistos) ---
    if len(test_df) > 0:
        proba = clf.predict_proba(X_test)[:, 1]
        preds = (proba >= 0.5).astype(int)
        print("\n--- Evaluación (hold-out temporal) ---")
        print(f"Accuracy:      {accuracy_score(y_test_cls, preds):.3f}")
        print(f"Log loss:      {log_loss(y_test_cls, proba):.3f}")
        print(f"Brier score:   {brier_score_loss(y_test_cls, proba):.3f}  (más bajo = mejor calibrado)")

        margin_preds = reg.predict(X_test)
        print(f"MAE margen:    {mean_absolute_error(y_test_reg, margin_preds):.2f} puntos")

        # Baseline de referencia: "gana siempre el local" y "gana quien tenga más Elo"
        baseline_home = accuracy_score(y_test_cls, np.ones(len(y_test_cls)))
        print(f"[Referencia] Acertar siempre con el local: {baseline_home:.3f}")
    else:
        print("No hay suficientes partidos para separar un conjunto de validación todavía.")

    # --- Importancia de features (útil para tu hermano: qué pesa más) ---
    importances = pd.Series(clf.feature_importances_, index=feature_cols).sort_values(ascending=False)
    print("\nTop 15 features más importantes (clasificador):")
    print(importances.head(15).to_string())

    # --- Guardado de artefactos ---
    joblib.dump(clf, MODELS_DIR / f"win_classifier_{MODEL_VERSION}.joblib")
    joblib.dump(reg, MODELS_DIR / f"margin_regressor_{MODEL_VERSION}.joblib")
    joblib.dump(feature_cols, MODELS_DIR / f"feature_columns_{MODEL_VERSION}.joblib")
    importances.to_csv(MODELS_DIR / f"feature_importance_{MODEL_VERSION}.csv")

    print(f"\nModelos guardados en {MODELS_DIR}")
    return clf, reg, feature_cols


if __name__ == "__main__":
    train()
