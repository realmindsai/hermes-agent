from dataclasses import dataclass


def _pick_number(*values: object) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        if isinstance(value, (int, float)):
            return value
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


@dataclass
class FsanzImportRow:
    food_id: str | None
    food_name: str | None
    energy_kcal: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    raw_payload: dict


def normalize_fsanz_row(row: dict) -> FsanzImportRow:
    return FsanzImportRow(
        food_id=row.get("Food ID"),
        food_name=row.get("Food Name"),
        energy_kcal=_pick_number(row.get("Energy, kcal")),
        protein_g=_pick_number(row.get("Protein, g")),
        carbs_g=_pick_number(row.get("Carbohydrate, g")),
        fat_g=_pick_number(row.get("Fat, g")),
        raw_payload=row,
    )

