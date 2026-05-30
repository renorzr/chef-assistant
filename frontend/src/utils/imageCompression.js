const DEFAULT_MAX_DIMENSION = 1600;
const DEFAULT_QUALITY = 0.82;
const OUTPUT_TYPE = "image/jpeg";

function loadImageFromFile(file) {
  return new Promise((resolve, reject) => {
    const objectUrl = URL.createObjectURL(file);
    const image = new Image();

    image.onload = () => {
      URL.revokeObjectURL(objectUrl);
      resolve(image);
    };

    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("Image preview failed."));
    };

    image.src = objectUrl;
  });
}

function canvasToBlob(canvas, type, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
      } else {
        reject(new Error("Image compression failed."));
      }
    }, type, quality);
  });
}

function getScaledSize(width, height, maxDimension) {
  const longestSide = Math.max(width, height);
  if (longestSide <= maxDimension) {
    return { width, height };
  }

  const scale = maxDimension / longestSide;
  return {
    width: Math.round(width * scale),
    height: Math.round(height * scale)
  };
}

function getCompressedFileName(fileName) {
  const baseName = fileName.replace(/\.[^.]+$/, "") || "image";
  return `${baseName}.jpg`;
}

export async function compressImageFile(file, { maxDimension = DEFAULT_MAX_DIMENSION, quality = DEFAULT_QUALITY } = {}) {
  const contentType = (file.type || "").toLowerCase();
  if (!contentType.startsWith("image/") || contentType === "image/gif") {
    return file;
  }

  const image = await loadImageFromFile(file);
  const { width, height } = getScaledSize(image.naturalWidth || image.width, image.naturalHeight || image.height, maxDimension);

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;

  const context = canvas.getContext("2d");
  if (!context) {
    return file;
  }

  context.drawImage(image, 0, 0, width, height);

  const blob = await canvasToBlob(canvas, OUTPUT_TYPE, quality);
  if (blob.size >= file.size) {
    return file;
  }

  return new File([blob], getCompressedFileName(file.name), {
    type: OUTPUT_TYPE,
    lastModified: Date.now()
  });
}
