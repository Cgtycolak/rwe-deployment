import numpy as np
import pandas as pd


def categorize_direction(values):
    """Categorize system direction values into YAL/YAT categories."""
    categorized = []
    for v in values:
        if v > 750:
            categorized.append("Strong YAL")
        elif v > 350:
            categorized.append("Normal YAL")
        elif v > 50:
            categorized.append("Weak YAL")
        elif v < -750:
            categorized.append("Strong YAT")
        elif v < -350:
            categorized.append("Normal YAT")
        elif v < -50:
            categorized.append("Weak YAT")
        else:
            categorized.append("Balanced")

    return categorized


def compute_confusion_matrix(actual_values, predicted_values):
    """Compute a normalized confusion matrix for YAL/YAT categories."""
    from sklearn.metrics import confusion_matrix

    labels = ["Strong YAL", "Normal YAL", "Weak YAL", "Balanced", "Weak YAT", "Normal YAT", "Strong YAT"]
    display_labels = [
        "Strong YAL<br>(750MW+)", "Normal YAL<br>(350-750MW)", "Weak YAL<br>(50-350MW)",
        "Balanced<br>(≈0MW)", "Weak YAT<br>(50-350MW)", "Normal YAT<br>(350-750MW)", "Strong YAT<br>(750MW+)"
    ]

    actual_cats    = categorize_direction(actual_values)
    predicted_cats = categorize_direction(predicted_values)

    cm = confusion_matrix(actual_cats, predicted_cats, labels=labels, normalize="pred")
    cm_real = confusion_matrix(actual_cats, predicted_cats, labels=labels)
    cm_data = [[round(float(v), 2) for v in row] for row in cm]

    return {
        'z':        cm_data,
        'x_labels': display_labels,
        'y_labels': display_labels,
        'labels':   labels,
    }
