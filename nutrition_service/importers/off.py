import json
from dataclasses import dataclass
from pathlib import Path


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
class OffImportRow:
    barcode: str | None
    product_name: str | None
    brand_name: str | None
    serving_size_text: str | None
    energy_kcal: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    raw_payload: dict


def load_off_records(path: str | Path) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("products"), list):
        return [row for row in payload["products"] if isinstance(row, dict)]
    raise ValueError("OFF import expects a JSON array or a {'products': [...]} object.")


def normalize_off_record(row: dict) -> OffImportRow:
    nutriments = row.get("nutriments") or {}
    return OffImportRow(
        barcode=row.get("code"),
        product_name=row.get("product_name"),
        brand_name=row.get("brands"),
        serving_size_text=row.get("serving_size"),
        energy_kcal=_pick_number(nutriments.get("energy-kcal_serving"), nutriments.get("energy-kcal_100g")),
        protein_g=_pick_number(nutriments.get("proteins_serving"), nutriments.get("proteins_100g")),
        carbs_g=_pick_number(nutriments.get("carbohydrates_serving"), nutriments.get("carbohydrates_100g")),
        fat_g=_pick_number(nutriments.get("fat_serving"), nutriments.get("fat_100g")),
        raw_payload=row,
    )
