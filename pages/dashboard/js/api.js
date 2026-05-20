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

export async function getSubscriptions(userId) {
  const params = userId ? { user_id: userId } : {};
  const result = await bridge.apiGet('subscriptions', params);
  const r = await handleResponse(result);
  return { items: r.items || [], total: r.total || 0 };
}

export async function getUsers() {
  const result = await bridge.apiGet('users');
  const r = await handleResponse(result);
  return { items: r.items || [], total: r.total || 0 };
}

export async function getFeeds() {
  const result = await bridge.apiGet('feeds');
  const r = await handleResponse(result);
  return { items: r.items || [], total: r.total || 0 };
}

export async function unsubscribe(subId, userId) {
  const payload = { sub_id: subId };
  if (userId) payload.user_id = userId;
  const result = await bridge.apiPost('unsubscribe', payload);
  return await handleResponse(result);
}

export async function updateSubscription(subId, options, userId) {
  const payload = { sub_id: subId, options };
  if (userId) payload.user_id = userId;
  const result = await bridge.apiPost('subscriptions/update', payload);
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

export async function getPluginSettings() {
  const result = await bridge.apiGet('plugin-settings');
  return await handleResponse(result);
}

export async function setPluginSettings({ subscription_defaults = {} } = {}) {
  const result = await bridge.apiPost('plugin-settings', { subscription_defaults });
  return await handleResponse(result);
}

export async function testSubscription(subId, userId) {
  const payload = { sub_id: subId };
  if (userId) payload.user_id = userId;
  const result = await bridge.apiPost('test-subscription', payload);
  return await handleResponse(result);
}

export async function batchActivate(subIds, userId) {
  const payload = { sub_ids: subIds };
  if (userId) payload.user_id = userId;
  const result = await bridge.apiPost('batch/activate', payload);
  return await handleResponse(result);
}

export async function batchDeactivate(subIds, userId) {
  const payload = { sub_ids: subIds };
  if (userId) payload.user_id = userId;
  const result = await bridge.apiPost('batch/deactivate', payload);
  return await handleResponse(result);
}

export async function batchUnsubscribe(subIds, userId) {
  const payload = { sub_ids: subIds };
  if (userId) payload.user_id = userId;
  const result = await bridge.apiPost('batch/unsubscribe', payload);
  return await handleResponse(result);
}

export async function getStats() {
  const result = await bridge.apiGet('stats');
  return await handleResponse(result);
}

let _prevCounter = 0;

export async function getPushHistory({ status = '', page = 1, pageSize = 20 } = {}) {
  const params = { page, page_size: pageSize };
  if (status) params.status = status;
  const result = await bridge.apiGet('push-history', params);
  const r = await handleResponse(result);
  return { items: r.items || [], total: r.total || 0, page: r.page || 1, page_size: r.page_size || pageSize };
}

export async function getRouteKbStatus() {
  const result = await bridge.apiGet('route-kb/status');
  return await handleResponse(result);
}

export async function syncRouteKb() {
  const result = await bridge.apiPost('route-kb/sync', {});
  return await handleResponse(result);
}

export async function getRouteKbTask() {
  const result = await bridge.apiGet('route-kb/task');
  return await handleResponse(result);
}

export async function deletePushHistory(historyId) {
  const result = await bridge.apiPost('push-history/delete', { history_id: historyId });
  return await handleResponse(result);
}

export async function cleanupPushHistory(days = 30) {
  const result = await bridge.apiPost('push-history/cleanup', { days });
  return await handleResponse(result);
}

export async function getUserDetails() {
  const result = await bridge.apiGet('users/detail');
  const r = await handleResponse(result);
  return { items: r.items || [], total: r.total || 0 };
}

export async function updateUser(userId, settings) {
  const result = await bridge.apiPost('users/update', { user_id: userId, settings });
  return await handleResponse(result);
}

export async function deleteUser(userId) {
  const result = await bridge.apiPost('users/delete', { user_id: userId });
  return await handleResponse(result);
}

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
