"""Train a small illustrative failure-risk classifier from labeled sample data."""
from pathlib import Path
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

ROOT = Path(__file__).parent
SAMPLES = [
    (44, .8, 1500, 0), (52, 1.2, 1480, 0), (62, 1.8, 1520, 0), (68, 2.2, 1460, 0),
    (72, 2.8, 1510, 0), (75, 3.0, 1500, 0), (79, 3.8, 1320, 1), (84, 4.8, 1650, 1),
    (88, 5.2, 1200, 1), (91, 6.0, 1770, 1), (81, 4.2, 1420, 1), (66, 4.5, 1490, 1),
    (70, 2.0, 1100, 1), (55, 1.0, 1500, 0), (60, 1.6, 1550, 0), (77, 2.4, 1480, 0),
    (73, 3.7, 1600, 1), (58, 3.9, 1450, 1), (48, .7, 1550, 0), (86, 2.9, 1510, 1),
]
data = np.array(SAMPLES, dtype=float)
X, y = data[:, :3], data[:, 3].astype(int)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=.25, random_state=17, stratify=y)
model = RandomForestClassifier(n_estimators=180, max_depth=5, class_weight="balanced", random_state=17)
model.fit(X_train, y_train)
print(classification_report(y_test, model.predict(X_test), zero_division=0))
out = ROOT / "model.joblib"
joblib.dump(model, out)
print(f"Saved model to {out}")
