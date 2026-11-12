# Predictive model

`train.py` uses the included labeled illustrative examples to train a Random Forest classifier and writes `model.joblib`. These examples demonstrate the workflow; they are not calibrated to any particular machine or plant. The API loads this model when present and otherwise clearly reports its deterministic demo fallback. Real deployments need validated, representative failure and healthy-operation data.
