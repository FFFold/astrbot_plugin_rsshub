const bridge = typeof window !== 'undefined' ? window.AstrBotPluginPage : null;

export async function ready() {
  if (!bridge) throw new Error('AstrBotPluginPage bridge not available');
  return await bridge.ready();
}

async function handleResponse(result) {
  if (result && result.ok !== undefined) {
    if (!result.ok) throw new Error(result.error || result.message || '操作失败');
    return result;
  }
  return result;
}

export async function getSubscriptions() {
  const result = await bridge.apiGet('subscriptions');
  const r = await handleResponse(result);
  return { items: r.items || [], total: r.total || 0 };
}

export async function subscribe(data) {
  const result = await bridge.apiPost('subscribe', data);
  return await handleResponse(result);
}

export async function unsubscribe(subId) {
  const result = await bridge.apiPost('unsubscribe', { sub_id: subId });
  return await handleResponse(result);
}

export async function updateSubscription(subId, options) {
  const result = await bridge.apiPost('subscriptions/update', { sub_id: subId, options });
  return await handleResponse(result);
}

export async function getFeedItems(feedId, page = 1, pageSize = 20) {
  const result = await bridge.apiGet('feeds/items', { feed_id: feedId, page, page_size: pageSize });
  return await handleResponse(result);
}

export async function refreshFeed(feedId) {
  const result = await bridge.apiPost('feeds/refresh', { feed_id: feedId });
  return await handleResponse(result);
}

export async function getSettings(userId) {
  const result = await bridge.apiGet('settings', { user_id: userId });
  return await handleResponse(result);
}

export async function setSettings(userId, settings) {
  const result = await bridge.apiPost('settings', { user_id: userId, settings });
  return await handleResponse(result);
}

export async function testSubscription(subId) {
  const result = await bridge.apiPost('test-subscription', { sub_id: subId });
  return await handleResponse(result);
}

export async function testUrl(url) {
  const result = await bridge.apiPost('test-url', { url });
  return await handleResponse(result);
}

export async function batchActivate(subIds) {
  const result = await bridge.apiPost('batch/activate', { sub_ids: subIds });
  return await handleResponse(result);
}

export async function batchDeactivate(subIds) {
  const result = await bridge.apiPost('batch/deactivate', { sub_ids: subIds });
  return await handleResponse(result);
}

export async function batchUnsubscribe(subIds) {
  const result = await bridge.apiPost('batch/unsubscribe', { sub_ids: subIds });
  return await handleResponse(result);
}

export async function getStats() {
  const result = await bridge.apiGet('stats');
  return await handleResponse(result);
}

export async function getExport(userId) {
  const result = await bridge.apiPost('export', { user_id: userId });
  return await handleResponse(result);
}

let _prevCounter = 0;

export async function checkUpdates() {
  try {
    const r = await bridge.apiGet('updates');
    const counter = r?.counter ?? 0;
    const changed = counter !== _prevCounter;
    _prevCounter = counter;
    return { changed };
  } catch {
    return { changed: false };
  }
}
