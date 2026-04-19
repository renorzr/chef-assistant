from typing import List, Optional, Dict
from pydantic import BaseModel, Field, ConfigDict


class RecipeIngredientCreate(BaseModel):
    name: str = Field(..., min_length=1)
    amount: Optional[str] = None
    unit: Optional[str] = None
    note: Optional[str] = None
    optional: bool = False
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
    note: Optional[str] = None
    optional: bool
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
    created_at: Optional[str] = None

    ingredients: List[RecipeIngredientRead]
    steps: List[RecipeStepRead]
    media: List[RecipeMediaRead]

    model_config = ConfigDict(from_attributes=True)


class RecipeListResponse(BaseModel):
    items: List[RecipeRead]
    page: int
    page_size: int
    total: int
    total_pages: int


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


class MenuCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    preference_text: Optional[str] = None


class MenuUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    preference_text: Optional[str] = None


class MenuSummaryRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    preference_text: Optional[str] = None
    item_count: int = 0


class MenuCategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    sort_order: int = 0


class MenuCategoryUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    sort_order: int = 0


class MenuCategoryRead(BaseModel):
    id: int
    menu_id: int
    name: str
    sort_order: int


class MenuItemCreateRequest(BaseModel):
    recipe_id: int = Field(..., ge=1)
    category_id: Optional[int] = None
    item_name_override: Optional[str] = None
    notes: Optional[str] = None
    sort_order: int = 0


class MenuItemUpdateRequest(BaseModel):
    recipe_id: int = Field(..., ge=1)
    category_id: Optional[int] = None
    item_name_override: Optional[str] = None
    notes: Optional[str] = None
    sort_order: int = 0


class MenuItemRead(BaseModel):
    id: int
    menu_id: int
    recipe_id: int
    recipe_name: str
    recipe_cover_image_url: Optional[str] = None
    recipe_cook_time_minutes: Optional[int] = None
    recipe_difficulty: Optional[str] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    item_name_override: Optional[str] = None
    notes: Optional[str] = None
    sort_order: int


class MenuRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    preference_text: Optional[str] = None
    categories: List[MenuCategoryRead]
    items: List[MenuItemRead]


class MenuGenerateFromTextRequest(BaseModel):
    name: str = Field(..., min_length=1)
    preference_text: str = Field(..., min_length=1)
    dish_count: Optional[int] = Field(default=None, ge=1, le=20)


class MenuGenerateFromTextResponse(BaseModel):
    menu: MenuRead
    generation_notes: List[str]
    score_breakdown: Dict[str, float]


class MealPlanItemRead(BaseModel):
    id: int
    meal_plan_id: int
    recipe_id: int
    recipe_name: str
    recipe_cover_image_url: Optional[str] = None
    recipe_cook_time_minutes: Optional[int] = None
    recipe_difficulty: Optional[str] = None
    sort_order: int
    notes: Optional[str] = None


class MealPlanRead(BaseModel):
    id: int
    name: str
    status: str
    expected_finish_at: Optional[str] = None
    completed_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    items: List[MealPlanItemRead]


class MealPlanSummaryRead(BaseModel):
    id: int
    name: str
    status: str
    item_count: int = 0
    expected_finish_at: Optional[str] = None
    completed_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    updated_at: Optional[str] = None


class MealPlanItemCreateRequest(BaseModel):
    recipe_id: int = Field(..., ge=1)
    on_expired: str = Field(default="ask")


class MealPlanUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1)


class MealPlanAddItemResponse(BaseModel):
    status: str
    message: str
    meal_plan: MealPlanRead



class ChatMessageRequest(BaseModel):
    session_id: Optional[str] = None
    message: str = Field(..., min_length=1)
    context: Dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ChatAction(BaseModel):
    type: str
    query: Optional[str] = None
    id: Optional[str] = None
    url: Optional[str] = None
    limit: Optional[int] = None


class ChatCard(BaseModel):
    type: str
    id: str
    title: str
    subtitle: Optional[str] = None
    image_url: Optional[str] = None


class ChatMessageResponse(BaseModel):
    session_id: str
    reply_text: str
    cards: List[ChatCard]
    action: Optional[ChatAction] = None


class ChatHistoryMessage(BaseModel):
    id: int
    role: str
    content: str
    cards: List[ChatCard] = Field(default_factory=list)
    created_at: Optional[str] = None


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: List[ChatHistoryMessage]


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


class RecipeImportFromHtmlItem(BaseModel):
    source_url: str = Field(..., min_length=1)
    html: str = Field(..., min_length=1)


class RecipeImportFromHtmlRequest(BaseModel):
    recipes: List[RecipeImportFromHtmlItem] = Field(..., min_length=1)


class RecipeImportFromHtmlResult(BaseModel):
    source_url: str
    status: str
    recipe_id: Optional[int] = None
    recipe_name: Optional[str] = None
    message: str


class RecipeImportFromHtmlResponse(BaseModel):
    results: List[RecipeImportFromHtmlResult]


class RecipeImportFromTextRequest(BaseModel):
    text: str = Field(..., min_length=1)


class RecipeImportFromTextResponse(BaseModel):
    recipe: RecipeRead
    message: str


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
