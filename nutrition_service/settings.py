import os


class NutritionSettings:
    def __init__(self) -> None:
        self.database_url = os.getenv(
            "NUTRITION_SERVICE_DATABASE_URL",
            "postgresql+psycopg://nutrition:nutrition@localhost:5432/nutrition",
        )
        self.bind_host = os.getenv("NUTRITION_SERVICE_BIND_HOST", "127.0.0.1")
        self.bind_port = int(os.getenv("NUTRITION_SERVICE_BIND_PORT", "8781"))
