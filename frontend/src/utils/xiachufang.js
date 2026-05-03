export function normalizeXiachufangRecipeUrl(url) {
  const match = url.trim().match(/^https?:\/\/(?:www\.)?xiachufang\.com\/recipe\/(\d+)(?:\/|[?#].*)*$/i);
  if (!match) {
    return null;
  }
  return `https://www.xiachufang.com/recipe/${match[1]}/`;
}
