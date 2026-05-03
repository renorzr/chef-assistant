import React from "react";
import { ImageOrPlaceholder } from "./common";
import { formatDifficulty } from "../utils/recipeDisplay";

export function RecipeCard({ recipe, subtitle, onClick, footer, overlayActions }) {
  return (
    <div className="relative mb-2 rounded-2xl bg-white p-3 shadow">
      <div onClick={onClick} className="cursor-pointer">
        <ImageOrPlaceholder
          src={recipe.cover_image_url}
          alt={recipe.name}
          className="mb-2 h-32 w-full rounded-xl object-cover"
          placeholderClassName="mb-2 h-32 rounded-xl bg-gray-200"
        />
        <div className="font-semibold">{recipe.name}</div>
        <div className="text-xs text-gray-500">{subtitle || `⏱${recipe.cook_time_minutes}min ⭐${formatDifficulty(recipe.difficulty)}`}</div>
      </div>

      {overlayActions ? <div className="absolute bottom-3 right-3 flex gap-2">{overlayActions}</div> : null}
      {footer ? <div className="mt-2">{footer}</div> : null}
    </div>
  );
}

export function LinkCard({ title, type, subtitle, onClick }) {
  return (
    <div onClick={onClick} className="mb-2 cursor-pointer rounded-xl bg-gray-100 p-3">
      <div className="text-xs text-gray-500">{type}</div>
      <div className="font-semibold">{title}</div>
      {subtitle ? <div className="mt-1 text-xs text-gray-500">{subtitle}</div> : null}
    </div>
  );
}

export function ChatMessage({ role, children }) {
  return (
    <div className={`mb-3 flex ${role === "user" ? "justify-end" : "justify-start"}`}>
      <div className={`max-w-[80%] rounded-2xl p-3 ${role === "user" ? "bg-black text-white" : "bg-white"}`}>{children}</div>
    </div>
  );
}
