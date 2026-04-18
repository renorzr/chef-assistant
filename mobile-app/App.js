import React, { useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, SafeAreaView, StyleSheet, Text, TextInput, View } from 'react-native';
import { StatusBar } from 'expo-status-bar';
import { WebView } from 'react-native-webview';

const APP_WEB_URL = 'http://10.0.2.2:5173';
const API_BASE_URL = 'http://10.0.2.2:8000';

function extractRecipeLinks(html) {
  const matches = Array.from(html.matchAll(/https?:\/\/(?:www\.)?xiachufang\.com\/recipe\/\d+\/?/g));
  const seen = new Set();
  const links = [];
  for (const match of matches) {
    const url = match[0].replace(/\/?$/, '/').replace('http://', 'https://');
    if (!seen.has(url)) {
      seen.add(url);
      links.push(url);
    }
  }
  return links;
}

export default function App() {
  const mainWebViewRef = useRef(null);
  const importWebViewRef = useRef(null);

  const [mainUrl, setMainUrl] = useState(APP_WEB_URL);
  const [importSession, setImportSession] = useState(null);
  const [importStatus, setImportStatus] = useState('idle');
  const [importMessage, setImportMessage] = useState('');
  const [manualUrl, setManualUrl] = useState(APP_WEB_URL);

  const importPageUrl = useMemo(() => importSession?.currentUrl || importSession?.url || null, [importSession]);

  const sendImportResultToWeb = (payload) => {
    const script = `window.dispatchEvent(new CustomEvent('native-import-result', { detail: ${JSON.stringify(payload)} })); true;`;
    mainWebViewRef.current?.injectJavaScript(script);
  };

  const handleMainMessage = (event) => {
    try {
      console.log('[rn.bridge] main message raw', event.nativeEvent.data);
      const message = JSON.parse(event.nativeEvent.data);
      console.log('[rn.bridge] main message parsed', message);
      if (message?.type === 'open_xiachufang_import') {
        const payload = message.payload || {};
        setImportSession({
          mode: payload.mode,
          url: payload.url || 'https://www.xiachufang.com/',
          currentUrl: payload.url || 'https://www.xiachufang.com/',
          phase: payload.mode === 'homepage' ? 'homepage_ready' : 'recipe_ready',
          queue: [],
          collectedRecipes: []
        });
        setImportStatus('waiting');
        setImportMessage(payload.mode === 'homepage' ? '请在当前首页完成验证，然后点击“开始导入首页推荐菜”。' : '请在当前页面完成人机验证，然后点击“提交当前页面”。');
        console.log('[rn.import] session opened', payload);
      }
    } catch {
      // ignore malformed bridge messages
    }
  };

  const submitCurrentImportPage = () => {
    if (!importWebViewRef.current) return;
    setImportStatus('capturing');
    setImportMessage('正在提取页面内容...');
    console.log('[rn.import] submit current page', importSession);
    importWebViewRef.current.injectJavaScript(`
      (function() {
        const payload = {
          type: 'page_html',
          url: location.href,
          html: document.documentElement.outerHTML
        };
        window.ReactNativeWebView.postMessage(JSON.stringify(payload));
      })();
      true;
    `);
  };

  const importRecipesFromHtml = async (recipes) => {
    setImportStatus('submitting');
    setImportMessage('正在提交后端导入...');
    console.log('[rn.import] submit from-html', { count: recipes.length, urls: recipes.map((r) => r.source_url) });
    const response = await fetch(`${API_BASE_URL}/recipes/import/from-html`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipes })
    });
    const payload = await response.json();
    console.log('[rn.import] from-html response', payload);
    if (!response.ok) {
      throw new Error(payload.detail || '导入失败');
    }
    return payload;
  };

  const handleImportMessage = async (event) => {
    try {
      console.log('[rn.import] import webview raw message', event.nativeEvent.data);
      const message = JSON.parse(event.nativeEvent.data);
      console.log('[rn.import] import webview parsed message', message?.type, message?.url);
      if (message?.type !== 'page_html') return;

      if (importSession?.mode === 'recipe') {
        const result = await importRecipesFromHtml([
          {
            source_url: message.url,
            html: message.html
          }
        ]);
        setImportStatus('done');
        setImportMessage('导入完成。');
        sendImportResultToWeb({ status: 'success', results: result.results || [] });
        closeImportModal();
      }

      if (importSession?.mode === 'homepage' && importSession.phase === 'homepage_ready') {
        const links = extractRecipeLinks(message.html).slice(0, 10);
        if (links.length === 0) {
          throw new Error('首页中未提取到推荐菜链接');
        }

        setImportSession((prev) => ({
          ...prev,
          queue: links,
          collectedRecipes: [],
          phase: 'collecting_recipe_pages',
          currentUrl: links[0]
        }));
        setImportStatus('capturing');
        setImportMessage(`已提取 ${links.length} 个推荐菜链接，正在抓取第 1 个菜谱页面...`);
        return;
      }

      if (importSession?.mode === 'homepage' && importSession.phase === 'collecting_recipe_pages') {
        const queue = importSession.queue || [];
        const collected = [...(importSession.collectedRecipes || []), { source_url: message.url, html: message.html }];

        if (collected.length < queue.length) {
          const nextUrl = queue[collected.length];
          setImportSession((prev) => ({
            ...prev,
            collectedRecipes: collected,
            currentUrl: nextUrl
          }));
          setImportStatus('capturing');
          setImportMessage(`正在抓取第 ${collected.length + 1} 个菜谱页面...`);
          return;
        }

        const result = await importRecipesFromHtml(collected);
        setImportStatus('done');
        setImportMessage('首页推荐菜导入完成。');
        sendImportResultToWeb({ status: 'success', results: result.results || [] });
        closeImportModal();
      }
    } catch (error) {
      setImportStatus('error');
      setImportMessage(error.message || '导入失败');
      sendImportResultToWeb({ status: 'failed', message: error.message || '导入失败' });
    }
  };

  const closeImportModal = () => {
    console.log('[rn.import] close import modal');
    setImportSession(null);
    setImportStatus('idle');
    setImportMessage('');
  };

  const handleImportLoadEnd = () => {
    console.log('[rn.import] import webview load end', importSession?.phase, importSession?.currentUrl);
    if (!importSession || importSession.mode !== 'homepage') return;
    if (importSession.phase !== 'collecting_recipe_pages') return;

    setTimeout(() => {
      submitCurrentImportPage();
    }, 1200);
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="dark" />

      <View style={styles.devBar}>
        <TextInput value={manualUrl} onChangeText={setManualUrl} style={styles.urlInput} autoCapitalize="none" autoCorrect={false} />
        <Pressable style={styles.urlButton} onPress={() => setMainUrl(manualUrl.trim() || APP_WEB_URL)}>
          <Text style={styles.urlButtonText}>打开</Text>
        </Pressable>
      </View>

      <WebView
        ref={mainWebViewRef}
        source={{ uri: mainUrl }}
        onMessage={handleMainMessage}
        javaScriptEnabled
        domStorageEnabled
        originWhitelist={['*']}
      />

      <Modal visible={!!importSession} animationType="slide" onRequestClose={closeImportModal}>
        <SafeAreaView style={styles.modalContainer}>
          <View style={styles.modalHeader}>
            <Pressable onPress={closeImportModal} style={styles.headerButton}>
              <Text>关闭</Text>
            </Pressable>
            <Text style={styles.modalTitle}>{importSession?.mode === 'homepage' ? '导入下厨房首页' : '导入下厨房菜谱'}</Text>
            <Pressable onPress={submitCurrentImportPage} style={styles.headerButton}>
              <Text>{importSession?.mode === 'homepage' && importSession?.phase === 'homepage_ready' ? '开始导入首页推荐菜' : '提交当前页面'}</Text>
            </Pressable>
          </View>

          <View style={styles.statusBar}>
            {importStatus === 'submitting' || importStatus === 'capturing' ? <ActivityIndicator size="small" color="#111827" /> : null}
            <Text style={styles.statusText}>{importMessage}</Text>
          </View>

          {importPageUrl ? (
            <WebView
              ref={importWebViewRef}
              source={{ uri: importPageUrl }}
              onMessage={handleImportMessage}
              onLoadEnd={handleImportLoadEnd}
              javaScriptEnabled
              domStorageEnabled
              sharedCookiesEnabled
              thirdPartyCookiesEnabled
              originWhitelist={['*']}
            />
          ) : null}
        </SafeAreaView>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#ffffff'
  },
  devBar: {
    flexDirection: 'row',
    paddingHorizontal: 12,
    paddingBottom: 8,
    gap: 8,
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb'
  },
  urlInput: {
    flex: 1,
    backgroundColor: '#f3f4f6',
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14
  },
  urlButton: {
    backgroundColor: '#111827',
    borderRadius: 12,
    paddingHorizontal: 14,
    paddingVertical: 10
  },
  urlButtonText: {
    color: '#ffffff',
    fontWeight: '600'
  },
  modalContainer: {
    flex: 1,
    backgroundColor: '#ffffff'
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#e5e7eb'
  },
  modalTitle: {
    fontSize: 16,
    fontWeight: '700'
  },
  headerButton: {
    paddingHorizontal: 8,
    paddingVertical: 6,
    backgroundColor: '#f3f4f6',
    borderRadius: 10
  },
  statusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: '#f9fafb'
  },
  statusText: {
    fontSize: 13,
    color: '#4b5563',
    flex: 1
  }
});
