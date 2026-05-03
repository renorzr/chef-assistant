import React from "react";
import { BottomSheet, ErrorBlock, IconButton, ImageOrPlaceholder, LoadingBlock } from "./common";

export function MenuPickerSheet({ open, menus, loading, error, onRetry, onClose, onPick, savingMenuId }) {
  return (
    <BottomSheet open={open} title="加入菜单" onClose={onClose}>
      {loading ? <LoadingBlock /> : null}
      {error ? <ErrorBlock onRetry={onRetry} /> : null}
      {!loading && !error ? (
        <div className="space-y-2 pb-2">
          {menus.map((menu) => (
            <button
              key={menu.id}
              onClick={() => onPick(menu.id)}
              disabled={savingMenuId === menu.id}
              className="flex w-full items-center justify-between rounded-2xl bg-gray-50 p-3 text-left disabled:opacity-40"
            >
              <div>
                <div className="font-medium">{menu.name}</div>
                <div className="text-xs text-gray-500">{menu.item_count} 道菜</div>
              </div>
              <div className="text-sm text-gray-500">{savingMenuId === menu.id ? "加入中" : "加入"}</div>
            </button>
          ))}
        </div>
      ) : null}
    </BottomSheet>
  );
}

export function MenuItemActionSheet({ open, onClose, onEditCategory, onRemove, removing }) {
  return (
    <BottomSheet open={open} title="更多操作" onClose={onClose}>
      <div className="space-y-2 pb-2">
        <button onClick={onEditCategory} className="w-full rounded-2xl bg-gray-50 p-3 text-left">
          修改分类
        </button>
        <button onClick={onRemove} disabled={removing} className="w-full rounded-2xl bg-red-50 p-3 text-left text-red-600 disabled:opacity-40">
          {removing ? "移出中" : "移出菜单"}
        </button>
      </div>
    </BottomSheet>
  );
}

export function CategoryPickerSheet({
  open,
  categories,
  currentCategoryId,
  currentCategoryName,
  creating,
  error,
  newCategoryName,
  setNewCategoryName,
  selectedCategoryId,
  setSelectedCategoryId,
  onClose,
  onSubmit
}) {
  return (
    <BottomSheet open={open} title="修改分类" onClose={onClose}>
      <div className="space-y-3 pb-2">
        <div className="text-xs text-gray-500">当前分类：{currentCategoryName || "未分类"}</div>

        <div className="space-y-2">
          <button
            onClick={() => {
              setSelectedCategoryId("");
              setNewCategoryName("");
            }}
            className={`w-full rounded-2xl p-3 text-left ${selectedCategoryId === "" && !newCategoryName.trim() ? "bg-black text-white" : "bg-gray-50"}`}
          >
            不分类
          </button>
          {categories.map((category) => (
            <button
              key={category.id}
              onClick={() => {
                setSelectedCategoryId(String(category.id));
                setNewCategoryName("");
              }}
              className={`w-full rounded-2xl p-3 text-left ${String(category.id) === selectedCategoryId ? "bg-black text-white" : "bg-gray-50"}`}
            >
              {category.name}
            </button>
          ))}
        </div>

        <div>
          <div className="mb-1 text-xs text-gray-500">或者输入新分类名称</div>
          <input
            value={newCategoryName}
            onChange={(e) => {
              setNewCategoryName(e.target.value);
              if (e.target.value.trim()) {
                setSelectedCategoryId("");
              }
            }}
            placeholder="例如：热菜 / 主食 / 甜点"
            className="w-full rounded-xl bg-gray-100 p-2"
          />
        </div>

        {error ? <div className="text-xs text-red-500">{error}</div> : null}

        <button onClick={onSubmit} disabled={creating} className="w-full rounded-xl bg-black p-3 text-white disabled:opacity-40">
          {creating ? "保存中" : "确认"}
        </button>
      </div>
    </BottomSheet>
  );
}

export function RecipeActionSheet({ open, title = "操作", options, onClose }) {
  return (
    <BottomSheet open={open} title={title} onClose={onClose}>
      <div className="space-y-2 pb-2">
        {options.map((option) => (
          <button
            key={option.label}
            onClick={option.onClick}
            disabled={option.disabled}
            className={`w-full rounded-2xl p-3 text-left ${option.tone === "danger" ? "bg-red-50 text-red-600" : "bg-gray-50"} disabled:opacity-40`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                {option.icon ? <span className="w-5 text-center text-base leading-none">{option.icon}</span> : null}
                <span>{option.label}</span>
              </div>
              {option.loading ? <span className="text-sm text-gray-500">{option.loadingLabel || option.label}</span> : null}
            </div>
          </button>
        ))}
      </div>
    </BottomSheet>
  );
}

export function ExpiredMealPlanSheet({ open, onClose, onContinue, onComplete, onCancelPlan, loadingAction }) {
  return (
    <BottomSheet open={open} title="当前餐单已过期" onClose={onClose}>
      <div className="space-y-2 pb-2">
        <div className="mb-2 text-sm text-gray-500">这个编辑中的餐单已经超过预计完成时间，请选择如何处理。</div>
        <button onClick={onContinue} disabled={!!loadingAction} className="w-full rounded-2xl bg-gray-50 p-3 text-left disabled:opacity-40">
          {loadingAction === "continue" ? "处理中" : "继续使用这个餐单"}
        </button>
        <button onClick={onComplete} disabled={!!loadingAction} className="w-full rounded-2xl bg-gray-50 p-3 text-left disabled:opacity-40">
          {loadingAction === "complete" ? "处理中" : "完成这个餐单"}
        </button>
        <button onClick={onCancelPlan} disabled={!!loadingAction} className="w-full rounded-2xl bg-red-50 p-3 text-left text-red-600 disabled:opacity-40">
          {loadingAction === "cancel" ? "处理中" : "取消这个餐单"}
        </button>
      </div>
    </BottomSheet>
  );
}

export function RecipeCreateSheet({ open, title, placeholder, value, onChange, onClose, onSubmit, submitting, submitLabel, error, inputProps = {} }) {
  const { multiline, ...restInputProps } = inputProps;

  return (
    <BottomSheet open={open} title={title} onClose={onClose}>
      <div className="space-y-3 pb-2">
        {multiline ? (
          <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="min-h-40 w-full rounded-2xl bg-gray-100 p-3 outline-none" {...restInputProps} />
        ) : (
          <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className="w-full rounded-2xl bg-gray-100 p-3 outline-none" {...restInputProps} />
        )}

        {error ? <div className="text-sm text-red-500">{error}</div> : null}

        <button onClick={onSubmit} disabled={submitting} className="w-full rounded-2xl bg-black p-3 text-white disabled:opacity-40">
          {submitting ? "处理中" : submitLabel}
        </button>
      </div>
    </BottomSheet>
  );
}

export function RecipeBasicInfoSheet({ open, values, onChange, onFileChange, previewUrl, onClose, onSubmit, saving, error }) {
  return (
    <BottomSheet open={open} title="编辑基础信息" onClose={onClose}>
      <div className="space-y-3 pb-2">
        <div>
          <div className="mb-1 text-sm font-medium">标题</div>
          <input value={values.name} onChange={(e) => onChange({ ...values, name: e.target.value })} className="w-full rounded-2xl bg-gray-100 p-3 outline-none" />
        </div>
        <div>
          <div className="mb-1 text-sm font-medium">耗时（分钟）</div>
          <input type="number" min="1" value={values.cook_time_minutes} onChange={(e) => onChange({ ...values, cook_time_minutes: e.target.value })} className="w-full rounded-2xl bg-gray-100 p-3 outline-none" />
        </div>
        <div>
          <div className="mb-1 text-sm font-medium">难度</div>
          <select value={values.difficulty} onChange={(e) => onChange({ ...values, difficulty: e.target.value })} className="w-full rounded-2xl bg-gray-100 p-3 outline-none">
            <option value="easy">简单</option>
            <option value="medium">普通</option>
            <option value="hard">困难</option>
          </select>
        </div>
        <div>
          <div className="mb-1 text-sm font-medium">主图</div>
          {previewUrl ? <ImageOrPlaceholder src={previewUrl} alt="主图预览" className="mb-2 h-40 w-full rounded-xl object-cover" placeholderClassName="mb-2 h-40 w-full rounded-xl bg-gray-100" /> : <div className="mb-2 rounded-xl bg-gray-100 p-4 text-sm text-gray-500">当前没有主图</div>}
          <input type="file" accept="image/*" onChange={(e) => onFileChange(e.target.files?.[0] || null)} className="block w-full text-sm text-gray-600" />
        </div>
        {error ? <div className="text-sm text-red-500">{error}</div> : null}
        <button onClick={onSubmit} disabled={saving} className="w-full rounded-2xl bg-black p-3 text-white disabled:opacity-40">
          {saving ? "保存中" : "保存"}
        </button>
      </div>
    </BottomSheet>
  );
}

export function RecipeIngredientsSheet({ open, ingredients, onChange, onClose, onSubmit, saving, error }) {
  const updateRow = (index, patch) => {
    onChange(ingredients.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  };

  const removeRow = (index) => {
    onChange(ingredients.filter((_, itemIndex) => itemIndex !== index));
  };

  const addRow = () => {
    onChange([...ingredients, { name: "", amount: "", unit: "" }]);
  };

  return (
    <BottomSheet open={open} title="编辑食材" onClose={onClose}>
      <div className="space-y-3 pb-2">
        <div className="max-h-[60vh] space-y-3 overflow-auto pr-1">
          {ingredients.map((item, index) => (
            <div key={index} className="rounded-2xl bg-gray-50 p-3">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-sm font-medium">食材 {index + 1}</div>
                <button onClick={() => removeRow(index)} className="text-sm text-red-500">
                  删除
                </button>
              </div>
              <div className="space-y-2">
                <input value={item.name} onChange={(e) => updateRow(index, { name: e.target.value })} placeholder="食材名称" className="w-full rounded-xl bg-white p-3 outline-none" />
                <div className="flex gap-2">
                  <input value={item.amount} onChange={(e) => updateRow(index, { amount: e.target.value })} placeholder="数量" className="flex-1 rounded-xl bg-white p-3 outline-none" />
                  <input value={item.unit} onChange={(e) => updateRow(index, { unit: e.target.value })} placeholder="单位" className="w-24 rounded-xl bg-white p-3 outline-none" />
                </div>
              </div>
            </div>
          ))}
        </div>
        <button onClick={addRow} className="w-full rounded-2xl bg-gray-100 p-3 text-sm">
          新增食材
        </button>
        {error ? <div className="text-sm text-red-500">{error}</div> : null}
        <button onClick={onSubmit} disabled={saving} className="w-full rounded-2xl bg-black p-3 text-white disabled:opacity-40">
          {saving ? "保存中" : "保存"}
        </button>
      </div>
    </BottomSheet>
  );
}

export function RecipeStepEditSheet({ open, step, instruction, onInstructionChange, onFileChange, previewUrl, onClose, onSubmit, saving, error }) {
  return (
    <BottomSheet open={open} title={step ? `编辑步骤 ${step.step_order}` : "编辑步骤"} onClose={onClose}>
      <div className="space-y-3 pb-2">
        <textarea value={instruction} onChange={(e) => onInstructionChange(e.target.value)} placeholder="步骤说明" className="min-h-32 w-full rounded-2xl bg-gray-100 p-3 outline-none" />
        <div>
          <div className="mb-1 text-sm font-medium">步骤图片</div>
          {previewUrl ? <ImageOrPlaceholder src={previewUrl} alt="步骤预览" className="mb-2 max-h-80 w-full rounded-xl object-contain" placeholderClassName="mb-2 h-32 w-full rounded-xl bg-gray-100" /> : <div className="mb-2 rounded-xl bg-gray-100 p-4 text-sm text-gray-500">当前没有图片</div>}
          <input type="file" accept="image/*" onChange={(e) => onFileChange(e.target.files?.[0] || null)} className="block w-full text-sm text-gray-600" />
        </div>
        {error ? <div className="text-sm text-red-500">{error}</div> : null}
        <button onClick={onSubmit} disabled={saving} className="w-full rounded-2xl bg-black p-3 text-white disabled:opacity-40">
          {saving ? "保存中" : "保存"}
        </button>
      </div>
    </BottomSheet>
  );
}
