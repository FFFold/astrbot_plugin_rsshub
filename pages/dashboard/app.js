import {
  ready,
  getSubscriptions,
  unsubscribe,
  updateSubscription,
  getFeedItems,
  refreshFeed,
  testSubscription,
  batchActivate,
  batchDeactivate,
  batchUnsubscribe,
  getStats,
  checkUpdates,
  getPluginSettings,
  getHandlerSchema,
  setPluginSettings,
  getUsers,
  getFeeds,
  getPushHistory,
  getRouteKbStatus,
  syncRouteKb,
  getRouteKbTask,
  deletePushHistory,
  cleanupPushHistory,
  getUserDetails,
  updateUser,
  deleteUser,
} from './js/api.js';
import { initTheme } from './js/theme.js';

let toastTimer = null;
let routeKbPollTimer = null;

const FALLBACK_HANDLER_SCHEMA = {
  handlers: [
    {
      type: 'builtin',
      name: 'xml_parse',
      title: 'XML/HTML 解析',
      description: '解析 XML/HTML 标签内容为正文和媒体组件',
      fields: [],
    },
    {
      type: 'builtin',
      name: 'ai_transform',
      title: 'AI 改写',
      description: '调用 AstrBot LLM 能力对正文做改写、总结或格式化',
      fields: [
        { name: 'prompt', label: '提示词', type: 'text', default: '', placeholder: '例如：请总结为三条要点' },
      ],
    },
  ],
};

function normalizeUserState(state) {
  return Number(state) < 0 ? -1 : 1;
}

function formatUserState(state) {
  return normalizeUserState(state) < 0 ? '已封禁' : '用户';
}

function formatDate(iso) {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
}

function normalizeHandlers(handlers) {
  if (!Array.isArray(handlers)) return [];
  return handlers
    .filter(item => item && typeof item === 'object')
    .map(item => ({
      id: String(item.id || '').trim(),
      type: String(item.type || 'builtin').trim() || 'builtin',
      name: String(item.name || '').trim(),
      status: Number.isFinite(Number(item.status)) ? Number(item.status) : -100,
      config: item.config && typeof item.config === 'object' ? { ...item.config } : {},
    }))
    .filter(item => item.id && item.name);
}

function normalizeHandlerSchema(schema) {
  const items = Array.isArray(schema?.handlers) ? schema.handlers : Array.isArray(schema) ? schema : FALLBACK_HANDLER_SCHEMA.handlers;
  return items
    .filter(item => item && typeof item === 'object')
    .map(item => {
      const type = String(item.type || 'builtin').trim() || 'builtin';
      const name = String(item.name || item.id || '').trim();
      return {
        type,
        name,
        id: String(item.id || `${type}.${name}`).trim(),
        title: String(item.title || item.label || name || '未命名 Handler'),
        description: String(item.description || ''),
        fields: Array.isArray(item.fields) ? item.fields.map(field => ({
          name: String(field.name || '').trim(),
          label: String(field.label || field.title || field.name || ''),
          type: String(field.type || 'string').trim(),
          default: field.default,
          required: Boolean(field.required),
          placeholder: String(field.placeholder || ''),
          options: Array.isArray(field.options) ? field.options : [],
        })).filter(field => field.name) : [],
      };
    })
    .filter(item => item.name);
}

function getHandlerSchemaEntry(schema, handler) {
  return schema.find(item => item.type === handler.type && item.name === handler.name)
    || schema.find(item => item.name === handler.name)
    || null;
}

function defaultValueForField(field) {
  if (field.default !== undefined) return cloneJsonValue(field.default);
  if (field.type === 'bool') return false;
  if (field.type === 'int' || field.type === 'float') return 0;
  if (field.type === 'list[string]') return [];
  if (field.type === 'json') return {};
  return '';
}

function cloneJsonValue(value) {
  if (value === undefined || value === null) return value;
  if (typeof value !== 'object') return value;
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return Array.isArray(value) ? [...value] : { ...value };
  }
}

function handlersToEditorState(handlers) {
  const normalized = normalizeHandlers(handlers);
  return {
    handlers: normalized,
    handlers_advanced: false,
    handlers_json: JSON.stringify(normalized, null, 2),
  };
}

function buildHandlersFromEditorState(form) {
  if (form.handlers_advanced) {
    return normalizeHandlers(JSON.parse(form.handlers_json || '[]'));
  }
  return normalizeHandlers(form.handlers);
}

const store = PetiteVue.reactive({
  // Data
  subs: [],
  filteredSubs: [],
  stats: { total_subscriptions: 0, active_subscriptions: 0, total_feeds: 0, unique_users: 0 },
  loading: true,
  searchQuery: '',
  editMode: false,
  selectedIds: [],
  subPagination: { page: 1, pageSize: 20 },

  // Panel
  panelVisible: false,
  panelExpanded: false,
  panelMode: 'detail', // edit | detail

  // Edit form
  editForm: {
    id: 0, feed_id: 0, feed_title: '', feed_link: '', user_id: '',
    title: '', tags: '', target_session: '', interval: 10,
    notify: -100, state_: true, send_mode: -100, length_limit: -100,
    display_author: -100, display_via: -100, display_title: -100,
    display_entry_tags: -100, style: -100, display_media: -100,
    handlers_mode: 'inherit',
    handlers: [], handlers_json: '[]', handlers_advanced: false,
  },

  // Detail
  detailSub: {},
  detailItems: [],

  // Tabs / Settings / Users / Feeds
  activeTab: 'subs',
  selectedUserId: null,
  users: [],
  usersLoading: false,
  feeds: [],
  feedsLoading: false,
  pluginSettingsLoading: false,
  subscriptionDefaults: {
    interval: 10,
    notify: true,
    send_mode: '自动',
    length_limit: 0,
    display_author: '自动',
    display_via: '自动',
    display_title: '自动',
    display_entry_tags: false,
    style: 'RSStT',
    display_media: true,
  },

  // Push History
  pushHistory: [],
  pushHistoryLoading: false,
  pushHistoryFilter: { status: '', page: 1, pageSize: 20 },
  pushHistoryTotal: 0,

  // Route Knowledge
  routeKbLoading: false,
  routeKbSyncing: false,
  routeKbStatus: null,
  routeKbTask: null,

  // User Edit Panel
  userEditPanelVisible: false,
    userEditForm: {
      user_id: '',
      state: 1,
    interval: -100,
    notify: -100,
    send_mode: -100,
    length_limit: -100,
    display_author: -100,
    display_via: -100,
      display_title: -100,
      display_entry_tags: -100,
      style: -100,
      display_media: -100,
      default_target_session: '',
      handlers: [],
      handlers_json: '[]',
      handlers_advanced: false,
    },
  handlerSchema: normalizeHandlerSchema(FALLBACK_HANDLER_SCHEMA),

  // Feedback
  toast: { show: false, message: '', type: 'success' },
  dialog: { show: false, title: '', message: '', okText: '确定', okClass: 'btn-danger', resolve: null },

  // ─── Lifecycle ─────────────────────────────────

  async loadData(resetPage = true) {
    this.loading = true;
    try {
      const [subResult, statsResult] = await Promise.all([
        getSubscriptions(this.selectedUserId || undefined),
        getStats(),
      ]);
      this.subs = subResult.items;
      this.stats = statsResult.stats;
      this.filterSubs(resetPage);
    } catch (err) {
      this.showToast('加载失败: ' + err.message, 'error');
    } finally {
      this.loading = false;
    }
  },

  async loadUsers() {
    this.usersLoading = true;
    try {
      const result = await getUserDetails();
      this.users = result.items || [];
    } catch (err) {
      this.showToast('加载用户失败: ' + err.message, 'error');
    } finally {
      this.usersLoading = false;
    }
  },

  selectUser(userId) {
    this.selectedUserId = userId;
    this.activeTab = 'subs';
    this.loadData();
  },

  async loadFeeds() {
    this.feedsLoading = true;
    try {
      const result = await getFeeds();
      this.feeds = result.items || [];
    } catch (err) {
      this.showToast('加载 Feed 失败: ' + err.message, 'error');
    } finally {
      this.feedsLoading = false;
    }
  },

  async loadSettings() {
    this.pluginSettingsLoading = true;
    try {
      const pluginResult = await getPluginSettings();
      if (pluginResult.subscription_defaults) {
        this.subscriptionDefaults = {
          ...this.subscriptionDefaults,
          ...pluginResult.subscription_defaults,
        };
      }
    } catch (err) {
      this.showToast('加载设置失败: ' + err.message, 'error');
    } finally {
      this.pluginSettingsLoading = false;
    }
  },

  async loadHandlerSchema() {
    try {
      const result = await getHandlerSchema();
      this.handlerSchema = normalizeHandlerSchema(result);
    } catch {
      this.handlerSchema = normalizeHandlerSchema(FALLBACK_HANDLER_SCHEMA);
    }
  },

  async savePluginSettings() {
    try {
      const result = await setPluginSettings({
        subscription_defaults: this.subscriptionDefaults,
      });
      if (result.subscription_defaults) {
        this.subscriptionDefaults = {
          ...this.subscriptionDefaults,
          ...result.subscription_defaults,
        };
      }
      this.showToast(result.message || '插件设置已保存');
    } catch (err) {
      this.showToast('保存插件设置失败: ' + err.message, 'error');
    }
  },

  // ─── Search & Filter ──────────────────────────

  filterSubs(resetPage = true) {
    const q = this.searchQuery.toLowerCase().trim();
    if (!q) {
      this.filteredSubs = [...this.subs];
    } else {
      this.filteredSubs = this.subs.filter((s) =>
        (s.feed_title && s.feed_title.toLowerCase().includes(q)) ||
        (s.feed_link && s.feed_link.toLowerCase().includes(q)) ||
        (s.title && s.title.toLowerCase().includes(q)) ||
        (s.tags && s.tags.toLowerCase().includes(q)) ||
        (s.user_id && s.user_id.toLowerCase().includes(q)) ||
        String(s.id).includes(q)
      );
    }
    if (resetPage) {
      this.resetSubPage();
      this.selectedIds = [];
    }
    this.clampSubPage();
  },

  resetSubPage() {
    this.subPagination.page = 1;
  },

  clampSubPage() {
    const totalPages = this.subTotalPages();
    if (this.subPagination.page > totalPages) this.subPagination.page = totalPages;
    if (this.subPagination.page < 1) this.subPagination.page = 1;
  },

  subTotalPages() {
    const pageSize = this.subPagination.pageSize || 20;
    return Math.max(1, Math.ceil(this.filteredSubs.length / pageSize));
  },

  showSubPagination() {
    return this.filteredSubs.length > (this.subPagination.pageSize || 20);
  },

  pagedSubs() {
    this.clampSubPage();
    const pageSize = this.subPagination.pageSize || 20;
    const start = (this.subPagination.page - 1) * pageSize;
    return this.filteredSubs.slice(start, start + pageSize);
  },

  subPrevPage() {
    if (this.subPagination.page > 1) {
      this.subPagination.page--;
      this.selectedIds = [];
    }
  },

  subNextPage() {
    if (this.subPagination.page < this.subTotalPages()) {
      this.subPagination.page++;
      this.selectedIds = [];
    }
  },

  // ─── Edit Mode / Batch ────────────────────────

  toggleEditMode() {
    this.editMode = !this.editMode;
    if (!this.editMode) this.selectedIds = [];
  },

  toggleSelect(id) {
    const idx = this.selectedIds.indexOf(id);
    if (idx >= 0) this.selectedIds.splice(idx, 1);
    else this.selectedIds.push(id);
  },

  async batchActivate() {
    if (this.selectedIds.length === 0) return;
    try {
      await this.runBatchByUser((ids, userId) => batchActivate(ids, userId));
      this.showToast(`已启用 ${this.selectedIds.length} 个订阅`);
      this.selectedIds = [];
      await this.loadData();
    } catch (err) {
      this.showToast('批量启用失败: ' + err.message, 'error');
    }
  },

  async batchDeactivate() {
    if (this.selectedIds.length === 0) return;
    try {
      await this.runBatchByUser((ids, userId) => batchDeactivate(ids, userId));
      this.showToast(`已禁用 ${this.selectedIds.length} 个订阅`);
      this.selectedIds = [];
      await this.loadData();
    } catch (err) {
      this.showToast('批量禁用失败: ' + err.message, 'error');
    }
  },

  async batchUnsubscribe() {
    if (this.selectedIds.length === 0) return;
    const ok = await this.showConfirm(`确定取消 ${this.selectedIds.length} 个订阅？此操作不可恢复。`, '批量取消订阅', '取消订阅');
    if (!ok) return;
    try {
      await this.runBatchByUser((ids, userId) => batchUnsubscribe(ids, userId));
      this.showToast(`已取消 ${this.selectedIds.length} 个订阅`);
      this.selectedIds = [];
      await this.loadData();
    } catch (err) {
      this.showToast('批量取消失败: ' + err.message, 'error');
    }
  },

  // ─── Panel: Detail ────────────────────────────

  openDetailPanel(sub) {
    this.panelMode = 'detail';
    this.detailSub = { ...sub };
    this.detailItems = [];
    this.panelVisible = true;
  },

  switchToEdit(sub) {
    this.panelMode = 'edit';
    this.editForm = {
      id: sub.id, feed_id: sub.feed_id,
      feed_title: sub.feed_title, feed_link: sub.feed_link,
      user_id: sub.user_id,
      title: sub.title || '',
      tags: sub.tags || '',
      target_session: sub.target_session || '',
      interval: sub.interval ?? -100,
      state_: sub.state === 1,
      notify: sub.notify ?? -100,
      send_mode: sub.send_mode ?? -100,
      length_limit: sub.length_limit ?? -100,
      display_author: sub.display_author ?? -100,
      display_via: sub.display_via ?? -100,
      display_title: sub.display_title ?? -100,
      display_entry_tags: sub.display_entry_tags ?? -100,
      style: sub.style ?? -100,
      display_media: sub.display_media ?? -100,
      handlers_mode: sub.handlers_mode || 'inherit',
      ...handlersToEditorState(sub.handlers),
    };
  },

  async loadDetailItems(feedId) {
    if (!feedId) return;
    try {
      const r = await getFeedItems(feedId, 1, 10);
      this.detailItems = r.items || [];
    } catch (err) {
      this.showToast('加载条目失败: ' + err.message, 'error');
    }
  },

  async handleRefreshDetail(feedId) {
    if (!feedId) return;
    try {
      await refreshFeed(feedId);
      this.showToast('Feed 刷新完成');
    } catch (err) {
      this.showToast('刷新失败: ' + err.message, 'error');
    }
  },

  async handleTestDetail(subId) {
    if (!subId) return;
    try {
      const r = await testSubscription(subId, this.currentSubUserId());
      this.showToast(r.message || '测试完成');
    } catch (err) {
      this.showToast('测试失败: ' + err.message, 'error');
    }
  },

  // ─── Panel: Edit ──────────────────────────────

  async handleEditSub() {
    try {
      const options = {};
      if (this.editForm.title !== undefined) options.title = this.editForm.title;
      if (this.editForm.tags !== undefined) options.tags = this.editForm.tags;
      if (this.editForm.interval !== undefined) options.interval = this.editForm.interval;
      if (this.editForm.target_session !== undefined) options.target_session = this.editForm.target_session;
      if (this.editForm.length_limit !== undefined) options.length_limit = this.editForm.length_limit;
      options.handlers_mode = this.editForm.handlers_mode || 'inherit';
      if (options.handlers_mode === 'override') {
        options.handlers = buildHandlersFromEditorState(this.editForm);
      } else {
        options.handlers = [];
      }
      options.state = this.editForm.state_ ? 1 : 0;
      options.notify = this.editForm.notify;
      options.send_mode = this.editForm.send_mode;
      options.display_author = this.editForm.display_author;
      options.display_via = this.editForm.display_via;
      options.display_title = this.editForm.display_title;
      options.display_entry_tags = this.editForm.display_entry_tags;
      options.style = this.editForm.style;
      options.display_media = this.editForm.display_media;

      await updateSubscription(this.editForm.id, options, this.currentSubUserId());
      this.showToast('订阅已更新');
      this.closePanel();
      await this.loadData();
    } catch (err) {
      this.showToast('更新失败: ' + err.message, 'error');
    }
  },

  async handleDeleteSub() {
    const id = this.panelMode === 'edit' ? this.editForm.id : this.detailSub.id;
    if (!id) return;
    const ok = await this.showConfirm('确定删除此订阅？此操作不可恢复。', '删除订阅', '删除');
    if (!ok) return;
    try {
      await unsubscribe(id, this.currentSubUserId());
      this.showToast('订阅已删除');
      this.closePanel();
      await this.loadData();
    } catch (err) {
      this.showToast('删除失败: ' + err.message, 'error');
    }
  },

  // ─── Panel Common ─────────────────────────────

  closePanel() {
    this.panelVisible = false;
  },

  // ─── Toast ────────────────────────────────────

  showToast(msg, type = 'success', duration = 3000) {
    if (toastTimer) clearTimeout(toastTimer);
    this.toast.show = true;
    this.toast.message = msg;
    this.toast.type = type;
    toastTimer = setTimeout(() => { this.toast.show = false; }, duration);
  },

  showConfirm(message, title = '确认', okText = '确定', okClass = 'btn-danger') {
    this.dialog.title = title;
    this.dialog.message = message;
    this.dialog.okText = okText;
    this.dialog.okClass = okClass;
    this.dialog.show = true;
    return new Promise((resolve) => {
      this.dialog.resolve = (result) => {
        this.dialog.show = false;
        resolve(result);
      };
    });
  },

  // ─── RSSHub Routes KB ────────────────────────

  async loadRouteKbStatus() {
    this.routeKbLoading = true;
    try {
      const result = await getRouteKbStatus();
      this.routeKbStatus = result.status || null;
      this.routeKbTask = this.routeKbStatus ? this.routeKbStatus.task : null;
      this.syncRouteKbPollingState();
    } catch (err) {
      this.showToast('加载知识库状态失败: ' + err.message, 'error');
    } finally {
      this.routeKbLoading = false;
    }
  },

  async handleRouteKbSync() {
    if (this.isRouteKbTaskRunning()) {
      this.showToast('当前已有知识库同步任务在运行，请等待完成后再试', 'error');
      this.startRouteKbPolling();
      return;
    }
    this.routeKbSyncing = true;
    try {
      const result = await syncRouteKb();
      this.routeKbTask = result.task || null;
      if (this.routeKbStatus) this.routeKbStatus.task = this.routeKbTask;
      this.syncRouteKbPollingState();
      this.showToast('知识库同步任务已启动');
    } catch (err) {
      this.showToast('启动同步失败: ' + err.message, 'error');
    } finally {
      this.routeKbSyncing = false;
    }
  },

  async refreshRouteKbTask() {
    try {
      const result = await getRouteKbTask();
      this.routeKbTask = result.task || null;
      if (this.routeKbStatus) this.routeKbStatus.task = this.routeKbTask;
      this.syncRouteKbPollingState();
    } catch (err) {
      this.showToast('刷新同步任务失败: ' + err.message, 'error');
    }
  },

  isRouteKbTaskRunning() {
    return !!(this.routeKbTask && ['queued', 'running'].includes(this.routeKbTask.status));
  },

  startRouteKbPolling() {
    if (routeKbPollTimer) return;
    routeKbPollTimer = setInterval(async () => {
      if (this.activeTab !== 'route-kb') return;
      await this.refreshRouteKbTask();
      if (!this.isRouteKbTaskRunning()) {
        this.stopRouteKbPolling();
        await this.loadRouteKbStatus();
      }
    }, 3000);
  },

  stopRouteKbPolling() {
    if (!routeKbPollTimer) return;
    clearInterval(routeKbPollTimer);
    routeKbPollTimer = null;
  },

  syncRouteKbPollingState() {
    if (this.isRouteKbTaskRunning()) {
      this.startRouteKbPolling();
      return;
    }
    this.stopRouteKbPolling();
  },

  // ─── Push History ─────────────────────────────

  async loadPushHistory() {
    this.pushHistoryLoading = true;
    try {
      const result = await getPushHistory({
        status: this.pushHistoryFilter.status,
        page: this.pushHistoryFilter.page,
        pageSize: this.pushHistoryFilter.pageSize,
      });
      this.pushHistory = result.items || [];
      this.pushHistoryTotal = result.total || 0;
      if (this.pushHistory.length === 0 && this.pushHistoryTotal > 0 && this.pushHistoryFilter.page > this.pushHistoryTotalPages()) {
        this.pushHistoryFilter.page = this.pushHistoryTotalPages();
        await this.loadPushHistory();
      }
    } catch (err) {
      this.showToast('加载推送历史失败: ' + err.message, 'error');
    } finally {
      this.pushHistoryLoading = false;
    }
  },

  async deletePushHistoryItem(id) {
    const ok = await this.showConfirm('确定删除此记录？', '删除记录', '删除');
    if (!ok) return;
    try {
      await deletePushHistory(id);
      this.showToast('记录已删除');
      await this.loadPushHistory();
    } catch (err) {
      this.showToast('删除失败: ' + err.message, 'error');
    }
  },

  async cleanupPushHistory() {
    const days = await this.showConfirm('确定清理 30 天前的推送历史？', '清理历史', '清理');
    if (!days) return;
    try {
      await cleanupPushHistory(30);
      this.showToast('历史记录已清理');
      await this.loadPushHistory();
    } catch (err) {
      this.showToast('清理失败: ' + err.message, 'error');
    }
  },

  pushHistoryPrevPage() {
    if (this.pushHistoryFilter.page > 1) {
      this.pushHistoryFilter.page--;
      this.loadPushHistory();
    }
  },

  pushHistoryNextPage() {
    const maxPage = this.pushHistoryTotalPages();
    if (this.pushHistoryFilter.page < maxPage) {
      this.pushHistoryFilter.page++;
      this.loadPushHistory();
    }
  },

  pushHistoryTotalPages() {
    const pageSize = this.pushHistoryFilter.pageSize || 20;
    return Math.max(1, Math.ceil(this.pushHistoryTotal / pageSize));
  },

  showPushHistoryPagination() {
    return this.pushHistoryTotal > (this.pushHistoryFilter.pageSize || 20);
  },

  // ─── User Management ────────────────────────────

  openUserEditPanel(user) {
    this.userEditForm = {
      user_id: user.user_id,
      state: normalizeUserState(user.state ?? 1),
      interval: user.interval ?? -100,
      notify: user.notify ?? -100,
      send_mode: user.send_mode ?? -100,
      length_limit: user.length_limit ?? -100,
      display_author: user.display_author ?? -100,
      display_via: user.display_via ?? -100,
      display_title: user.display_title ?? -100,
      display_entry_tags: user.display_entry_tags ?? -100,
      style: user.style ?? -100,
      display_media: user.display_media ?? -100,
      default_target_session: user.default_target_session || '',
      ...handlersToEditorState(user.handlers),
    };
    this.userEditPanelVisible = true;
  },

  closeUserEditPanel() {
    this.userEditPanelVisible = false;
  },

  async handleSaveUserEdit() {
    try {
      const settings = {
        state: normalizeUserState(this.userEditForm.state),
        interval: this.userEditForm.interval,
        notify: this.userEditForm.notify,
        send_mode: this.userEditForm.send_mode,
        length_limit: this.userEditForm.length_limit,
        display_author: this.userEditForm.display_author,
        display_via: this.userEditForm.display_via,
        display_title: this.userEditForm.display_title,
        display_entry_tags: this.userEditForm.display_entry_tags,
        style: this.userEditForm.style,
        display_media: this.userEditForm.display_media,
      };
      settings.default_target_session = this.userEditForm.default_target_session.trim();
      settings.handlers = buildHandlersFromEditorState(this.userEditForm);
      await updateUser(this.userEditForm.user_id, settings);
      this.showToast('用户配置已更新');
      this.closeUserEditPanel();
      await this.loadUsers();
    } catch (err) {
      this.showToast('更新失败: ' + err.message, 'error');
    }
  },

  async handleDeleteUser(userId) {
    const ok = await this.showConfirm(
      `确定删除用户 ${userId}？此操作将同时删除该用户的所有订阅，不可恢复。`,
      '删除用户',
      '删除'
    );
    if (!ok) return;
    try {
      await deleteUser(userId);
      this.showToast('用户已删除');
      await this.loadUsers();
    } catch (err) {
      this.showToast('删除失败: ' + err.message, 'error');
    }
  },

  // ─── Util ─────────────────────────────────────

  currentSubUserId() {
    const subUserId = this.panelMode === 'edit' ? this.editForm.user_id : this.detailSub.user_id;
    return subUserId || this.selectedUserId || undefined;
  },

  selectedSubsByUser() {
    const selected = new Set(this.selectedIds);
    return this.filteredSubs
      .filter((sub) => selected.has(sub.id))
      .reduce((groups, sub) => {
        const userId = sub.user_id || this.selectedUserId || undefined;
        const key = userId || '';
        if (!groups[key]) groups[key] = { userId, ids: [] };
        groups[key].ids.push(sub.id);
        return groups;
      }, {});
  },

  async runBatchByUser(action) {
    const groups = Object.values(this.selectedSubsByUser());
    for (const group of groups) {
      await action(group.ids, group.userId);
    }
  },

  handlerKey(handler) {
    return `${handler.type || 'builtin'}.${handler.name || handler.id || ''}`;
  },

  handlerTitle(handler) {
    const schema = getHandlerSchemaEntry(this.handlerSchema, handler);
    return schema?.title || handler.name || handler.id || '未命名 Handler';
  },

  handlerDescription(handler) {
    return getHandlerSchemaEntry(this.handlerSchema, handler)?.description || '';
  },

  handlerFields(handler) {
    return getHandlerSchemaEntry(this.handlerSchema, handler)?.fields || [];
  },

  availableBuiltinHandlers(form) {
    const active = new Set((form.handlers || []).map(item => this.handlerKey(item)));
    return this.handlerSchema.filter(item => !active.has(`${item.type}.${item.name}`));
  },

  addBuiltinHandler(form, key) {
    const schema = this.handlerSchema.find(item => `${item.type}.${item.name}` === key);
    if (!schema) return;
    const config = {};
    for (const field of schema.fields || []) config[field.name] = defaultValueForField(field);
    form.handlers.push({
      id: `${schema.type}.${schema.name}.${Date.now()}`,
      type: schema.type,
      name: schema.name,
      status: 1,
      config,
    });
    this.syncHandlersJson(form);
  },

  removeHandler(form, index) {
    form.handlers.splice(index, 1);
    this.syncHandlersJson(form);
  },

  moveHandler(form, index, direction) {
    const nextIndex = index + direction;
    if (nextIndex < 0 || nextIndex >= form.handlers.length) return;
    const [item] = form.handlers.splice(index, 1);
    form.handlers.splice(nextIndex, 0, item);
    this.syncHandlersJson(form);
  },

  syncHandlersJson(form) {
    form.handlers_json = JSON.stringify(normalizeHandlers(form.handlers), null, 2);
  },

  applyHandlersJson(form) {
    try {
      form.handlers = normalizeHandlers(JSON.parse(form.handlers_json || '[]'));
      form.handlers_json = JSON.stringify(form.handlers, null, 2);
      this.showToast('处理链 JSON 已应用');
    } catch (err) {
      this.showToast('处理链 JSON 格式错误: ' + err.message, 'error');
    }
  },

  ensureHandlerConfig(handler, field) {
    if (!handler.config || typeof handler.config !== 'object') handler.config = {};
    if (handler.config[field.name] === undefined) handler.config[field.name] = defaultValueForField(field);
    return handler.config[field.name];
  },

  updateHandlerField(form, handler, field, value) {
    if (!handler.config || typeof handler.config !== 'object') handler.config = {};
    if (field.type === 'int') {
      handler.config[field.name] = Number.isFinite(Number(value)) ? parseInt(value, 10) : 0;
    } else if (field.type === 'float') {
      handler.config[field.name] = Number.isFinite(Number(value)) ? parseFloat(value) : 0;
    } else if (field.type === 'list[string]') {
      handler.config[field.name] = String(value || '').split('\n').map(item => item.trim()).filter(Boolean);
    } else if (field.type === 'json') {
      try {
        handler.config[field.name] = JSON.parse(value || 'null');
      } catch {
        handler.config[field.name] = value;
      }
    } else {
      handler.config[field.name] = value;
    }
    this.syncHandlersJson(form);
  },

  handlerFieldValue(handler, field) {
    const value = this.ensureHandlerConfig(handler, field);
    if (field.type === 'list[string]') return Array.isArray(value) ? value.join('\n') : String(value || '');
    if (field.type === 'json') {
      if (typeof value === 'string') return value;
      try {
        return JSON.stringify(value, null, 2);
      } catch {
        return String(value ?? '');
      }
    }
    return value;
  },

  formatDate,
  formatUserState,
});

window.store = store;

let pollTimer = null;

initTheme();
ready()
  .then(() => {
    store.loadHandlerSchema();
    store.loadData();
    pollTimer = setInterval(async () => {
      const { changed } = await checkUpdates();
      if (changed) store.loadData(false);
    }, 10000);
    window.addEventListener('beforeunload', () => {
      if (pollTimer) clearInterval(pollTimer);
      if (routeKbPollTimer) clearInterval(routeKbPollTimer);
    });
  })
  .catch((err) => store.showToast('初始化失败: ' + err.message, 'error'));

PetiteVue.createApp(store).mount('.container');
