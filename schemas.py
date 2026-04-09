from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


class RecipeIngredientCreate(BaseModel):
    name: str = Field(..., min_length=1)
    amount: Optional[str] = None
    unit: Optional[str] = None
    is_main: bool = False


class RecipeStepCreate(BaseModel):
    step_order: int = Field(..., ge=1)
    instruction: str = Field(..., min_length=1)
    image_url: Optional[str] = None


class RecipeMediaCreate(BaseModel):
    media_type: str = Field(default="image")
    url: str = Field(..., min_length=1)


class RecipeCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    cook_time_minutes: int = Field(default=30, ge=1)
    difficulty: str = Field(default="medium")
    tags: List[str] = Field(default_factory=list)

    source_type: str = Field(default="user")
    source_url: Optional[str] = None
    cover_image_url: Optional[str] = None

    main_ingredient: Optional[str] = None
    dish_type: str = Field(default="other")
    cooking_method: str = Field(default="other")

    ingredients: List[RecipeIngredientCreate] = Field(default_factory=list)
    steps: List[RecipeStepCreate] = Field(default_factory=list)
    media: List[RecipeMediaCreate] = Field(default_factory=list)


class RecipeIngredientRead(BaseModel):
    id: int
    ingredient_id: int
    name: str
    amount: Optional[str] = None
    unit: Optional[str] = None
    is_main: bool

    model_config = ConfigDict(from_attributes=True)


class RecipeStepRead(BaseModel):
    id: int
    step_order: int
    instruction: str
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RecipeMediaRead(BaseModel):
    id: int
    media_type: str
    url: str

    model_config = ConfigDict(from_attributes=True)


class RecipeRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    cook_time_minutes: int
    difficulty: str
    tags: List[str]

    source_type: str
    source_url: Optional[str] = None
    cover_image_url: Optional[str] = None

    main_ingredient: Optional[str] = None
    dish_type: str
    cooking_method: str

    ingredients: List[RecipeIngredientRead]
    steps: List[RecipeStepRead]
    media: List[RecipeMediaRead]

    model_config = ConfigDict(from_attributes=True)


class MenuGenerateRequest(BaseModel):
    people_count: int = Field(..., ge=1)
    dish_count: int = Field(..., ge=1)
    preferences: List[str] = Field(default_factory=list)
    available_ingredients: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)


class MenuDish(BaseModel):
    recipe_id: int
    name: str
    cook_time_minutes: int
    difficulty: str
    dish_type: str
    cooking_method: str
    main_ingredient: Optional[str] = None


class MenuGenerateResponse(BaseModel):
    dishes: List[MenuDish]
    total_score: float
    score_breakdown: Dict[str, float]
    notes: List[str]


class VectorSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    max_cook_time_minutes: Optional[int] = Field(default=None, ge=1)
    difficulty: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class VectorSearchResult(BaseModel):
    recipe: RecipeRead
    score: float


class VectorSearchResponse(BaseModel):
    query: str
    results: List[VectorSearchResult]


class HybridSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1, le=50)
    semantic_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    max_cook_time_minutes: Optional[int] = Field(default=None, ge=1)
    difficulty: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class HybridSearchResult(BaseModel):
    recipe: RecipeRead
    score: float
    semantic_score: float
    keyword_score: float


class HybridSearchResponse(BaseModel):
    query: str
    semantic_weight: float
    results: List[HybridSearchResult]


class RecipeImportCreateRequest(BaseModel):
    url: str = Field(..., min_length=1)


class RecipeImportStatusResponse(BaseModel):
    job_id: int
    source_url: str
    status: str
    message: Optional[str] = None
    next_action: Optional[str] = None
    requires_user_intervention: bool


class RecipeImportResumeCookiesRequest(BaseModel):
    cookie: str = Field(..., min_length=1)


class RecipeImportSubmitHtmlRequest(BaseModel):
    html: str = Field(..., min_length=1)


class RecipeImportPreviewResponse(BaseModel):
    job_id: int
    status: str
    recipe: RecipeCreate


class RecipeImportCommitResponse(BaseModel):
    job_id: int
    status: str
    recipe: RecipeRead


class EmbeddingReindexRequest(BaseModel):
    only_missing: bool = False


class EmbeddingReindexResponse(BaseModel):
    total_recipes: int
    reindexed_count: int
    skipped_count: int
    failed_count: int
    message: str


class EmbeddingAuditStatusResponse(BaseModel):
    enabled: bool
    interval_seconds: int
    batch_size: int
    initial_delay_seconds: int
    total_recipes: int
    missing_embeddings: int
    last_run_at: Optional[str] = None
    last_repaired_count: int = 0
    last_failed_count: int = 0


class EmbeddingRepairMissingRequest(BaseModel):
    batch_size: int = Field(default=50, ge=1, le=1000)


class EmbeddingRepairMissingResponse(BaseModel):
    attempted_count: int
    repaired_count: int
    failed_count: int
    remaining_missing: int
    message: str
