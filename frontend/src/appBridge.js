function safeParse(data) {
  try {
    return JSON.parse(data);
  } catch {
    return null;
  }
}

export function isNativeApp() {
  return typeof window !== "undefined" && !!window.ReactNativeWebView;
}

export function openXiachufangImport(payload) {
  if (!isNativeApp()) {
    console.log("[bridge] open_xiachufang_import unavailable", { payload, hasNativeBridge: false });
    return false;
  }

  console.log("[bridge] open_xiachufang_import called", payload);

  window.ReactNativeWebView.postMessage(
    JSON.stringify({
      type: "open_xiachufang_import",
      payload
    })
  );
  return true;
}

export function subscribeImportResult(handler) {
  if (typeof window === "undefined") {
    return () => {};
  }

  const eventHandler = (event) => {
    const detail = event?.detail;
    if (detail) {
      handler(detail);
    }
  };

  const messageHandler = (event) => {
    const payload = safeParse(event?.data);
    if (payload?.type === "import_result") {
      console.log("[bridge] import_result received via window.message", payload.payload || {});
      handler(payload.payload || {});
    }
  };

  window.addEventListener("native-import-result", eventHandler);
  window.addEventListener("message", messageHandler);

  return () => {
    window.removeEventListener("native-import-result", eventHandler);
    window.removeEventListener("message", messageHandler);
  };
}
