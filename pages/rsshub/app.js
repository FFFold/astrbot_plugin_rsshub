import {
  ready,
  getSubscriptions,
  subscribe,
  unsubscribe,
  updateSubscription,
  getFeedItems,
  refreshFeed,
  testUrl,
  testSubscription,
  batchActivate,
  batchDeactivate,
  batchUnsubscribe,
  getStats,
  checkUpdates,
} from './js/api.js';
import { initTheme } from './js/theme.js';

let toastTimer = null;

function formatDate(iso) {
  if (!iso) return '-';
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch { return iso; }
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

  // Panel
  panelVisible: false,
  panelExpanded: false,
  panelMode: 'add', // add | edit | detail

  // Add form
  addForm: { url: '', title: '', tags: '', target_session: '', interval: 10 },
  testResult: null,

  // Edit form
  editForm: {
    id: 0, feed_id: 0, feed_title: '', feed_link: '', user_id: '',
    title: '', tags: '', target_session: '', interval: 10,
    notify_: true, state_: true, send_mode: 0, link_preview: 0,
    display_author: 0, display_via: 0, display_title: 0, style: 0,
  },

  // Detail
  detailSub: {},
  detailItems: [],

  // Feedback
  toast: { show: false, message: '', type: 'success' },
  dialog: { show: false, title: '', message: '', okText: '确定', okClass: 'btn-danger', resolve: null },

  // ─── Lifecycle ─────────────────────────────────

  async loadData() {
    this.loading = true;
    try {
      const [subResult, statsResult] = await Promise.all([
        getSubscriptions(),
        getStats(),
      ]);
      this.subs = subResult.items;
      this.stats = statsResult.stats;
      this.filterSubs();
    } catch (err) {
      this.showToast('加载失败: ' + err.message, 'error');
    } finally {
      this.loading = false;
    }
  },

  // ─── Search & Filter ──────────────────────────

  filterSubs() {
    const q = this.searchQuery.toLowerCase().trim();
    if (!q) {
      this.filteredSubs = [...this.subs];
      return;
    }
    this.filteredSubs = this.subs.filter((s) =>
      (s.feed_title && s.feed_title.toLowerCase().includes(q)) ||
      (s.feed_link && s.feed_link.toLowerCase().includes(q)) ||
      (s.title && s.title.toLowerCase().includes(q)) ||
      (s.tags && s.tags.toLowerCase().includes(q)) ||
      (s.user_id && s.user_id.toLowerCase().includes(q)) ||
      String(s.id).includes(q)
    );
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
      await batchActivate(this.selectedIds);
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
      await batchDeactivate(this.selectedIds);
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
      await batchUnsubscribe(this.selectedIds);
      this.showToast(`已取消 ${this.selectedIds.length} 个订阅`);
      this.selectedIds = [];
      await this.loadData();
    } catch (err) {
      this.showToast('批量取消失败: ' + err.message, 'error');
    }
  },

  // ─── Panel: Add ───────────────────────────────

  openAddPanel() {
    this.panelMode = 'add';
    this.addForm = { url: '', title: '', tags: '', target_session: '', interval: 10 };
    this.testResult = null;
    this.panelVisible = true;
  },

  async handleTestUrl() {
    const url = this.addForm.url.trim();
    if (!url) return;
    this.testResult = { loading: true };
    try {
      const r = await testUrl(url);
      this.testResult = r;
    } catch (err) {
      this.testResult = { error: err.message };
    }
  },

  async handleAddSub() {
    if (!this.addForm.url.trim()) {
      this.showToast('请输入 RSS 链接', 'error');
      return;
    }
    try {
      const data = { url: this.addForm.url.trim() };
      if (this.addForm.title) data.title = this.addForm.title.trim();
      if (this.addForm.tags) data.tags = this.addForm.tags.trim();
      if (this.addForm.target_session) data.target_session = this.addForm.target_session.trim();
      if (this.addForm.interval && this.addForm.interval > 0) data.interval = this.addForm.interval;

      await subscribe(data);
      this.showToast('订阅成功');
      this.closePanel();
      await this.loadData();
    } catch (err) {
      this.showToast('订阅失败: ' + err.message, 'error');
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
      interval: sub.interval || 10,
      state_: sub.state === 1,
      notify_: sub.notify === 1,
      send_mode: sub.send_mode ?? 0,
      link_preview: sub.link_preview ?? 0,
      display_author: sub.display_author ?? 0,
      display_via: sub.display_via ?? 0,
      display_title: sub.display_title ?? 0,
      style: sub.style ?? 0,
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
      const r = await testSubscription(subId);
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
      options.state = this.editForm.state_ ? 1 : 0;
      options.notify = this.editForm.notify_ ? 1 : 0;
      options.send_mode = this.editForm.send_mode;
      options.link_preview = this.editForm.link_preview;
      options.display_author = this.editForm.display_author;
      options.display_via = this.editForm.display_via;
      options.display_title = this.editForm.display_title;
      options.style = this.editForm.style;

      await updateSubscription(this.editForm.id, options);
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
      await unsubscribe(id);
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

  // ─── Util ─────────────────────────────────────

  formatDate,
});

window.store = store;

let pollTimer = null;

initTheme();
ready()
  .then(() => {
    store.loadData();
    pollTimer = setInterval(async () => {
      const { changed } = await checkUpdates();
      if (changed) store.loadData();
    }, 10000);
  })
  .catch((err) => store.showToast('初始化失败: ' + err.message, 'error'));

PetiteVue.createApp(store).mount('.container');
