from sqlalchemy import select, func
from sqlalchemy.orm import Session

from models import Recipe
from schemas import RecipeCreate, RecipeIngredientCreate, RecipeStepCreate, RecipeMediaCreate
from services.recipe_service import create_recipe


def seed_sample_data(db: Session) -> None:
    count = db.execute(select(func.count(Recipe.id))).scalar_one()
    if count > 0:
        return

    samples = [
        RecipeCreate(
            name="Garlic Chicken Stir Fry",
            description="Quick chicken stir fry with broccoli and soy.",
            cook_time_minutes=25,
            difficulty="easy",
            tags=["chicken", "quick", "weeknight"],
            source_type="user",
            cover_image_url=None,
            main_ingredient="chicken",
            dish_type="meat",
            cooking_method="fry",
            ingredients=[
                RecipeIngredientCreate(name="chicken breast", amount="300", unit="g", is_main=True),
                RecipeIngredientCreate(name="broccoli", amount="200", unit="g"),
                RecipeIngredientCreate(name="garlic", amount="3", unit="cloves"),
                RecipeIngredientCreate(name="soy sauce", amount="2", unit="tbsp"),
            ],
            steps=[
                RecipeStepCreate(step_order=1, instruction="Slice chicken and broccoli.", image_url=None),
                RecipeStepCreate(step_order=2, instruction="Stir-fry garlic and chicken in hot oil.", image_url=None),
                RecipeStepCreate(step_order=3, instruction="Add broccoli and soy sauce, cook until done.", image_url=None),
            ],
            media=[],
        ),
        RecipeCreate(
            name="Steamed Eggplant with Sesame",
            description="Light vegetable dish with sesame dressing.",
            cook_time_minutes=20,
            difficulty="easy",
            tags=["vegetable", "light", "healthy"],
            source_type="imported",
            source_url=None,
            cover_image_url=None,
            main_ingredient="eggplant",
            dish_type="vegetable",
            cooking_method="steam",
            ingredients=[
                RecipeIngredientCreate(name="eggplant", amount="2", unit="pcs", is_main=True),
                RecipeIngredientCreate(name="sesame oil", amount="1", unit="tbsp"),
                RecipeIngredientCreate(name="soy sauce", amount="1", unit="tbsp"),
                RecipeIngredientCreate(name="garlic", amount="1", unit="clove"),
            ],
            steps=[
                RecipeStepCreate(step_order=1, instruction="Slice eggplant into strips.", image_url=None),
                RecipeStepCreate(step_order=2, instruction="Steam for 10-12 minutes until tender.", image_url=None),
                RecipeStepCreate(step_order=3, instruction="Mix dressing and pour over eggplant.", image_url=None),
            ],
            media=[],
        ),
        RecipeCreate(
            name="Tomato Egg Soup",
            description="Comforting soup with tomato and egg ribbons.",
            cook_time_minutes=15,
            difficulty="easy",
            tags=["soup", "quick", "comfort"],
            source_type="user",
            cover_image_url=None,
            main_ingredient="tomato",
            dish_type="other",
            cooking_method="soup",
            ingredients=[
                RecipeIngredientCreate(name="tomato", amount="2", unit="pcs", is_main=True),
                RecipeIngredientCreate(name="egg", amount="2", unit="pcs"),
                RecipeIngredientCreate(name="spring onion", amount="1", unit="stalk"),
                RecipeIngredientCreate(name="salt", amount="1", unit="tsp"),
            ],
            steps=[
                RecipeStepCreate(step_order=1, instruction="Boil chopped tomato in water for 5 minutes.", image_url=None),
                RecipeStepCreate(step_order=2, instruction="Season soup and slowly pour beaten egg.", image_url=None),
                RecipeStepCreate(step_order=3, instruction="Garnish with spring onion.", image_url=None),
            ],
            media=[],
        ),
        RecipeCreate(
            name="Pan-Seared Salmon and Asparagus",
            description="Simple salmon fillet with asparagus.",
            cook_time_minutes=30,
            difficulty="medium",
            tags=["fish", "protein", "pan-seared"],
            source_type="imported",
            source_url=None,
            cover_image_url=None,
            main_ingredient="salmon",
            dish_type="meat",
            cooking_method="sear",
            ingredients=[
                RecipeIngredientCreate(name="salmon", amount="2", unit="fillets", is_main=True),
                RecipeIngredientCreate(name="asparagus", amount="200", unit="g"),
                RecipeIngredientCreate(name="lemon", amount="1", unit="pc"),
                RecipeIngredientCreate(name="salt", amount="1", unit="tsp"),
            ],
            steps=[
                RecipeStepCreate(step_order=1, instruction="Season salmon and asparagus.", image_url=None),
                RecipeStepCreate(step_order=2, instruction="Sear salmon skin-side down until crisp.", image_url=None),
                RecipeStepCreate(step_order=3, instruction="Cook asparagus in the same pan and finish with lemon.", image_url=None),
            ],
            media=[],
        ),
    ]

    for recipe in samples:
        create_recipe(db, recipe)
