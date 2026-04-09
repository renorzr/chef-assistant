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
    source_url = Column(String(1000), nullable=True)
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


class RecipeImportJob(Base):
    __tablename__ = "recipe_import_jobs"

    id = Column(Integer, primary_key=True, index=True)
    source_url = Column(String(1000), nullable=False)
    source_domain = Column(String(255), nullable=False, default="xiachufang.com")
    status = Column(String(50), nullable=False, default="pending")
    message = Column(Text, nullable=True)
    next_action = Column(String(100), nullable=True)

    cookie_header = Column(Text, nullable=True)
    fetched_html = Column(Text, nullable=True)
    parsed_recipe = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
