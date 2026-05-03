export function isUsableImage(url) {
  if (!url || typeof url !== "string") return false;
  if (url.includes("example.com")) return false;
  return true;
}

export function needsProxy(url) {
  if (!url || typeof url !== "string") return false;
  return url.includes("xiachufang.com") || url.includes("chuimg.com");
}

export function toDisplayImageUrl(url) {
  if (!isUsableImage(url)) return null;
  if (!needsProxy(url)) return url;
  return `/api/media/proxy?url=${encodeURIComponent(url)}`;
}
