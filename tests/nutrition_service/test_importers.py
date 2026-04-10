from nutrition_service.importers.fsanz import normalize_fsanz_row
from nutrition_service.importers.off import normalize_off_record
from nutrition_service.importers.usda import normalize_usda_food


def test_normalize_off_record_extracts_core_nutrients():
    row = {
        "code": "930000000001",
        "product_name": "Test Bar",
        "brands": "Test Brand",
        "serving_size": "50 g",
        "nutriments": {
            "energy-kcal_serving": 210,
            "proteins_serving": 20,
            "carbohydrates_serving": 15,
            "fat_serving": 7,
        },
    }

    normalized = normalize_off_record(row)

    assert normalized.barcode == "930000000001"
    assert normalized.product_name == "Test Bar"
    assert normalized.energy_kcal == 210
    assert normalized.protein_g == 20


def test_normalize_fsanz_row_extracts_generic_food_fields():
    row = {"Food ID": "A001", "Food Name": "Boiled egg", "Energy, kcal": "155", "Protein, g": "12.6"}

    normalized = normalize_fsanz_row(row)

    assert normalized.food_name == "Boiled egg"
    assert normalized.energy_kcal == 155
    assert normalized.protein_g == 12.6


def test_normalize_usda_food_extracts_serving_and_gtin():
    food = {
        "fdcId": 123,
        "description": "Protein Bar",
        "gtinUpc": "008181234567",
        "servingSize": 50,
        "servingSizeUnit": "g",
        "foodNutrients": [{"nutrientName": "Energy", "unitName": "KCAL", "value": 205}],
    }

    normalized = normalize_usda_food(food)

    assert normalized.fdc_id == 123
    assert normalized.gtin_upc == "008181234567"
    assert normalized.serving_size == 50
    assert normalized.energy_kcal == 205
