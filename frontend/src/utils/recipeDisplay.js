const DIFFICULTY_LABELS = {
  easy: "简单",
  medium: "普通",
  hard: "困难"
};

export const COOK_TIME_OPTIONS = [10, 20, 30, 40, 50, 60, 90, 120, 150, 180];

export function formatDifficulty(value) {
  return DIFFICULTY_LABELS[value] || value || "";
}

export function formatCookTimeOption(minutes) {
  if (minutes === 60) return "1小时";
  if (minutes === 90) return "1.5小时";
  if (minutes === 120) return "2小时";
  if (minutes === 150) return "2.5小时";
  if (minutes >= 180) return "3小时及以上";
  return `${minutes}分钟`;
}

export function nearestCookTimeOption(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return COOK_TIME_OPTIONS[2];
  }

  return COOK_TIME_OPTIONS.reduce((closest, option) => {
    return Math.abs(option - numericValue) < Math.abs(closest - numericValue) ? option : closest;
  }, COOK_TIME_OPTIONS[0]);
}
