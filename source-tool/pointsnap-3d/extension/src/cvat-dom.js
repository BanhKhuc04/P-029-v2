/*
 * Đọc giao diện CVAT và bấm hộ các nút có sẵn (A15).
 * Chỉ dùng tên lớp ổn định mà bộ test tự động của CVAT dùng; không đọc hay sửa trạng thái nội bộ của trang.
 * Mọi hàm "bấm hộ" trả về { ok, reason } để phần giao diện báo rõ và chuyển sang hướng dẫn thao tác tay.
 */
(function (root) {
  'use strict';

  const SEL = {
    frameInput: '.cvat-player-frame-selector input',
    filtersButton: '.cvat-annotation-header-filters-button',
    filtersModal: '.cvat-filters-modal-visible',
    recentButton: '.cvat-filters-modal-recently-used-button',
    recentDropdown: '.cvat-recently-used-filters-dropdown',
    submitButton: '.cvat-filters-modal-submit-button',
    cancelButton: '.cvat-filters-modal-cancel-button',
    sidebarItem: '.cvat-objects-sidebar-state-item',
    activeItem: '.cvat-objects-sidebar-state-active-item',
    attrWrapper: '.cvat-object-item-attribute-wrapper',
    labelSelector: '.cvat-objects-sidebar-state-item-label-selector',
    canvas3d: '.cvat-canvas3d-fullsize, .cvat-canvas3d-perspective, #cvat-canvas3d-wrapper',
  };

  const FILTERS_HISTORY = 'annotationFiltersHistory';

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  /** Chờ tới khi `probe()` trả về giá trị khác null/false, tối đa `timeout` ms. */
  async function waitFor(probe, timeout = 4000, step = 80) {
    const end = Date.now() + timeout;
    for (;;) {
      const value = probe();
      if (value) return value;
      if (Date.now() > end) return null;
      await sleep(step);
    }
  }

  const $ = (sel, scope) => (scope || document).querySelector(sel);

  function isVisible(el) {
    return !!el && el.getClientRects().length > 0;
  }

  /** Trang job đã dựng xong thanh điều khiển frame và danh sách đối tượng. */
  function workspaceReady() {
    return !!$(SEL.frameInput) && !!$('.cvat-objects-sidebar');
  }

  function currentFrame() {
    const input = $(SEL.frameInput);
    if (!input || input.value === '') return null;
    const n = Number(input.value);
    return Number.isFinite(n) ? n : null;
  }

  /** Gán giá trị cho ô nhập do React quản lý, như khi người dùng gõ. */
  function typeInto(input, value) {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(input, String(value));
    input.dispatchEvent(new Event('input', { bubbles: true }));
  }

  function pressEnter(el) {
    const init = { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true };
    el.dispatchEvent(new KeyboardEvent('keydown', init));
    el.dispatchEvent(new KeyboardEvent('keyup', init));
  }

  /** Chuyển tới `frame` bằng ô chọn frame của CVAT (không tải lại trang). */
  async function goToFrame(frame) {
    const input = $(SEL.frameInput);
    if (!input) return { ok: false, reason: 'Không thấy ô chọn frame của CVAT' };
    if (currentFrame() === frame) return { ok: true };
    input.focus();
    typeInto(input, frame);
    pressEnter(input);
    let moved = await waitFor(() => currentFrame() === frame, 1500);
    if (!moved) {
      // Ô chọn frame cũng chuyển frame khi mất focus.
      input.blur();
      moved = await waitFor(() => currentFrame() === frame, 1500);
    }
    input.blur();
    return moved ? { ok: true } : { ok: false, reason: `CVAT không chuyển sang frame ${frame}` };
  }

  /** Bộ lọc của CVAT đang bật (nút Filters có lớp `filters-armed`). */
  function filtersActive() {
    const button = $(SEL.filtersButton);
    return !!button && button.classList.contains('filters-armed');
  }

  /**
   * Thêm bộ lọc PointSnap vào "Recently used" của CVAT (lịch sử bộ lọc trong localStorage của trang),
   * như khi người dùng đã tự tạo bộ lọc này một lần. CVAT đọc lịch sử khi mở trang job.
   */
  function seedFilterHistory(logic) {
    let history = [];
    try {
      history = JSON.parse(window.localStorage.getItem(FILTERS_HISTORY) || '[]');
      if (!Array.isArray(history)) history = [];
    } catch (_) {
      history = [];
    }
    const key = JSON.stringify(logic);
    if (history.some((f) => JSON.stringify(f.logic) === key)) return false;
    const entry = { id: `pointsnap-${Date.now()}`, logic, keypointLogic: {} };
    window.localStorage.setItem(FILTERS_HISTORY, JSON.stringify([entry, ...history].slice(0, 10)));
    return true;
  }

  function closeFiltersModal() {
    const cancel = $(SEL.cancelButton);
    if (cancel) cancel.click();
  }

  /**
   * Bấm hộ: Filters → Recently used → mục có `attrName` → Submit.
   * Trả về { ok, reason, needsReload } — needsReload khi CVAT chưa nạp mục PointSnap vào lịch sử.
   */
  async function applyRecentFilter(attrName) {
    if (filtersActive()) return { ok: true, already: true };
    const button = $(SEL.filtersButton);
    if (!button) return { ok: false, reason: 'Không thấy nút Filters của CVAT' };
    button.click();
    const modal = await waitFor(() => $(SEL.filtersModal));
    if (!modal) return { ok: false, reason: 'Hộp thoại Filters không mở' };

    const recent = $(SEL.recentButton, modal);
    if (!recent || !isVisible(recent)) {
      closeFiltersModal();
      return { ok: false, needsReload: true, reason: 'CVAT chưa có bộ lọc PointSnap trong "Recently used"' };
    }
    recent.click();
    const item = await waitFor(() => {
      const menu = document.querySelector(`${SEL.recentDropdown}:not(.ant-popover-hidden)`);
      if (!menu) return null;
      return [...menu.querySelectorAll('[role="menuitem"], .ant-menu-item, .ant-dropdown-menu-item')]
        .find((el) => el.textContent.includes(attrName));
    });
    if (!item) {
      recent.click();
      closeFiltersModal();
      return { ok: false, needsReload: true, reason: 'CVAT chưa có bộ lọc PointSnap trong "Recently used"' };
    }
    item.click();
    const submit = await waitFor(() => {
      const el = $(SEL.submitButton);
      return el && !el.disabled ? el : null;
    }, 2000);
    if (!submit) {
      closeFiltersModal();
      return { ok: false, reason: 'Nút Submit của bộ lọc không bấm được' };
    }
    submit.click();
    const armed = await waitFor(filtersActive, 3000);
    return armed ? { ok: true } : { ok: false, reason: 'Đã bấm Submit nhưng bộ lọc chưa bật' };
  }

  /** Bấm hộ "Clear filters" trong hộp thoại Filters. */
  async function clearFilters() {
    if (!filtersActive()) return { ok: true };
    const button = $(SEL.filtersButton);
    if (!button) return { ok: false, reason: 'Không thấy nút Filters của CVAT' };
    button.click();
    const clear = await waitFor(() => $('.cvat-filters-modal-clear-button'));
    if (!clear) return { ok: false, reason: 'Không thấy nút Clear filters' };
    clear.click();
    const off = await waitFor(() => !filtersActive(), 3000);
    return off ? { ok: true } : { ok: false, reason: 'Bộ lọc chưa tắt' };
  }

  /** Nhãn hiển thị của một mục trong danh sách đối tượng. */
  function itemLabel(item) {
    const sel = $(SEL.labelSelector, item);
    if (!sel) return null;
    const chosen = sel.querySelector('.ant-select-selection-item');
    return chosen ? (chosen.getAttribute('title') || chosen.textContent || '').trim() : null;
  }

  function itemClientId(item) {
    const m = (item.id || '').match(/cvat-objects-sidebar-state-item-(\d+)$/);
    return m ? Number(m[1]) : null;
  }

  /** Giá trị thuộc tính `attrName` hiện trong khung chi tiết của mục (null nếu khung đang thu gọn). */
  function itemAttribute(item, attrName) {
    for (const wrapper of item.querySelectorAll(SEL.attrWrapper)) {
      const name = wrapper.querySelector('.cvat-text');
      if (name && name.textContent.trim() === attrName) {
        const field = wrapper.querySelector('textarea, input');
        return field ? field.value : null;
      }
    }
    return null;
  }

  /** Đối tượng đang được chọn / trỏ chuột trong CVAT: { clientId, label, flag } hoặc null. */
  function activeObject(attrName) {
    const item = $(SEL.activeItem);
    if (!item) return null;
    return { clientId: itemClientId(item), label: itemLabel(item), flag: itemAttribute(item, attrName) };
  }

  /** Các mục trong danh sách đối tượng bên phải (sau khi lọc chỉ còn box có cờ). */
  function sidebarItems() {
    return [...document.querySelectorAll(SEL.sidebarItem)].map((item) => ({
      el: item,
      clientId: itemClientId(item),
      label: itemLabel(item),
    }));
  }

  /**
   * Làm sáng box trên khung 3D bằng cách rê chuột vào mục của nó trong danh sách đối tượng,
   * giống người dùng rê chuột (CVAT kích hoạt đối tượng khi chuột đi vào mục).
   */
  function hoverItem(el) {
    if (!el) return false;
    el.scrollIntoView({ block: 'nearest' });
    el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, relatedTarget: document.body }));
    el.dispatchEvent(new MouseEvent('mouseenter', { bubbles: false, relatedTarget: document.body }));
    return true;
  }

  root.PointSnapCvat = {
    SEL,
    waitFor,
    workspaceReady,
    currentFrame,
    goToFrame,
    filtersActive,
    seedFilterHistory,
    applyRecentFilter,
    clearFilters,
    activeObject,
    sidebarItems,
    hoverItem,
  };
})(globalThis);
