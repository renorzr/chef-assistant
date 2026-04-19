from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Text,
    JSON,
    UniqueConstraint,
    DateTime,
    func,
)
from sqlalchemy.orm import relationship

from database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)

    cook_time_minutes = Column(Integer, nullable=False, default=30)
    difficulty = Column(String(50), nullable=False, default="medium")
    tags = Column(JSON, nullable=False, default=list)

    source_type = Column(String(50), nullable=False, default="user")
    source_url = Column(String(1000), nullable=True, unique=True, index=True)
    cover_image_url = Column(String(1000), nullable=True)

    main_ingredient = Column(String(255), nullable=True)
    dish_type = Column(String(50), nullable=False, default="other")
    cooking_method = Column(String(50), nullable=False, default="other")

    recipe_ingredients = relationship(
        "RecipeIngredient", back_populates="recipe", cascade="all, delete-orphan"
    )
    steps = relationship(
        "RecipeStep", back_populates="recipe", cascade="all, delete-orphan"
    )
    media = relationship(
        "RecipeMedia", back_populates="recipe", cascade="all, delete-orphan"
    )
    embedding = relationship(
        "RecipeEmbedding", back_populates="recipe", cascade="all, delete-orphan", uselist=False
    )


class Ingredient(Base):
    __tablename__ = "ingredients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)

    recipe_links = relationship("RecipeIngredient", back_populates="ingredient")


class RecipeIngredient(Base):
    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id", name="uq_recipe_ingredient"),
    )

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    ingredient_id = Column(Integer, ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False)

    amount = Column(String(50), nullable=True)
    unit = Column(String(50), nullable=True)
    note = Column(Text, nullable=True)
    optional = Column(Integer, nullable=False, default=0)
    is_main = Column(Integer, nullable=False, default=0)

    recipe = relationship("Recipe", back_populates="recipe_ingredients")
    ingredient = relationship("Ingredient", back_populates="recipe_links")


class RecipeStep(Base):
    __tablename__ = "recipe_steps"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    instruction = Column(Text, nullable=False)
    image_url = Column(String(1000), nullable=True)

    recipe = relationship("Recipe", back_populates="steps")


class RecipeMedia(Base):
    __tablename__ = "recipe_media"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="CASCADE"), nullable=False)
    media_type = Column(String(20), nullable=False, default="image")
    url = Column(String(1000), nullable=False)

    recipe = relationship("Recipe", back_populates="media")


class RecipeEmbedding(Base):
    __tablename__ = "recipe_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    recipe_id = Column(
        Integer,
        ForeignKey("recipes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    vector = Column(JSON, nullable=False)
    source_text = Column(Text, nullable=False)

    recipe = relationship("Recipe", back_populates="embedding")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_ref_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    cards_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("ChatSession", back_populates="messages")


class Menu(Base):
    __tablename__ = "menus"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    preference_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    categories = relationship("MenuCategory", back_populates="menu", cascade="all, delete-orphan")
    items = relationship("MenuItem", back_populates="menu", cascade="all, delete-orphan")


class MenuCategory(Base):
    __tablename__ = "menu_categories"
    __table_args__ = (
        UniqueConstraint("menu_id", "name", name="uq_menu_category_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(Integer, ForeignKey("menus.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    menu = relationship("Menu", back_populates="categories")
    items = relationship("MenuItem", back_populates="category")


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    menu_id = Column(Integer, ForeignKey("menus.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("menu_categories.id", ondelete="SET NULL"), nullable=True)

    item_name_override = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    menu = relationship("Menu", back_populates="items")
    category = relationship("MenuCategory", back_populates="items")
    recipe = relationship("Recipe")


class MealPlan(Base):
    __tablename__ = "meal_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="editing", index=True)
    expected_finish_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    items = relationship("MealPlanItem", back_populates="meal_plan", cascade="all, delete-orphan")


class MealPlanItem(Base):
    __tablename__ = "meal_plan_items"
    __table_args__ = (
        UniqueConstraint("meal_plan_id", "recipe_id", name="uq_meal_plan_recipe"),
    )

    id = Column(Integer, primary_key=True, index=True)
    meal_plan_id = Column(Integer, ForeignKey("meal_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    recipe_id = Column(Integer, ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)

    meal_plan = relationship("MealPlan", back_populates="items")
    recipe = relationship("Recipe")
