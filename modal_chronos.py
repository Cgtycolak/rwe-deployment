"""
Modal deployment for Chronos-2 inference using predict_df API.

Deploy with:
    modal deploy modal_chronos.py

Accepts fully feature-engineered train + covariate DataFrames built by
build_chronos_features() in utils.py and returns quantile forecasts via
pipeline.predict_df().
"""
import modal
from pydantic import BaseModel
from typing import Any, List, Optional

app = modal.App("rwe-chronos")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install([
        "chronos-forecasting==2.2.2",
        "torch",
        "numpy",
        "pandas",
        "fastapi[standard]",
    ])
)


class PredictPayload(BaseModel):
    train: List[Any]
    covariates: List[Any]
    prediction_length: int
    quantile_levels: Optional[List[float]] = [0.1, 0.5, 0.9]
    model: Optional[str] = "Model 1"


@app.cls(
    image=image,
    cpu=2.0,
    memory=6144,
    timeout=300,
    scaledown_window=2,
)
class ChronosForecaster:
    @modal.enter()
    def load(self):
        import torch
        from chronos import BaseChronosPipeline
        self.pipeline = BaseChronosPipeline.from_pretrained(
            "amazon/chronos-2",
            device_map="cpu",
            dtype=torch.bfloat16,
        )
        print("Chronos-2 (amazon/chronos-2) loaded.")

    @modal.fastapi_endpoint(method="POST", label="chronos-predict")
    def predict(self, payload: PredictPayload):
        import pandas as pd

        train_df          = pd.DataFrame(payload.train)
        cov_df            = pd.DataFrame(payload.covariates)
        prediction_length = payload.prediction_length
        quantile_levels   = payload.quantile_levels

        train_df['date'] = pd.to_datetime(train_df['date'])
        cov_df['date']   = pd.to_datetime(cov_df['date'])

        print(f"train shape: {train_df.shape}, cov shape: {cov_df.shape}, n={prediction_length}")
        print(f"train cols: {list(train_df.columns)}")

        pred_df = self.pipeline.predict_df(
            train_df,
            cov_df,
            id_column='id',
            timestamp_column='date',
            target='system_direction',
            prediction_length=prediction_length,
            quantile_levels=quantile_levels,
        )

        # Return all quantile columns so caller can select best_q dynamically
        q_cols = [c for c in pred_df.columns if c not in ('id', 'date', 'target_name', 'predictions')]
        return {
            "dates":     pred_df['date'].astype(str).tolist(),
            "quantiles": {col: pred_df[col].tolist() for col in q_cols},
        }
