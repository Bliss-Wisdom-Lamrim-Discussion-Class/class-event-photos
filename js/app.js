/**
 * GitHub Photo Gallery Web Application
 * Features:
 * - Commit/Push Pagination with Commit Message as Title
 * - 4 Color Themes (Light, Dark, Vintage, Cyberpunk)
 * - Lightbox Fullscreen Photo Viewer
 * - Dynamic Thumbnail & Image Fallback Rendering
 */

document.addEventListener('DOMContentLoaded', () => {
  // App State
  const state = {
    data: null,
    commits: [],
    currentPage: 1,
    itemsPerPage: 1, // 每頁顯示一個 Commit / Push
    currentTheme: localStorage.getItem('gallery-theme') || 'light',
    lightbox: {
      isOpen: false,
      commitIndex: 0,
      photoIndex: 0
    }
  };

  // DOM Elements
  const galleryContainer = document.getElementById('gallery-container');
  const paginationContainer = document.getElementById('pagination');
  const themeButtons = document.querySelectorAll('.theme-btn');
  
  // Lightbox DOM Elements
  const lightboxModal = document.getElementById('lightbox-modal');
  const lightboxImg = document.getElementById('lightbox-img');
  const lightboxTitle = document.getElementById('lightbox-title');
  const lightboxSubtext = document.getElementById('lightbox-subtext');
  const lightboxClose = document.getElementById('lightbox-close');
  const lightboxPrev = document.getElementById('lightbox-prev');
  const lightboxNext = document.getElementById('lightbox-next');

  // 初始化主題
  function initTheme() {
    applyTheme(state.currentTheme);
    themeButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        const theme = btn.getAttribute('data-set-theme');
        applyTheme(theme);
      });
    });
  }

  function applyTheme(theme) {
    state.currentTheme = theme;
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('gallery-theme', theme);

    themeButtons.forEach(btn => {
      if (btn.getAttribute('data-set-theme') === theme) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });
  }

  // 載入 JSON 資料
  async function loadGalleryData() {
    try {
      const response = await fetch('gallery-data.json');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      state.data = await response.json();
      state.commits = state.data.commits || [];
      
      if (state.commits.length === 0) {
        renderEmptyState();
        return;
      }

      renderGallery();
      renderPagination();
    } catch (error) {
      console.error('Failed to load gallery-data.json:', error);
      renderErrorState();
    }
  }

  // 渲染相簿（依 Commit 分頁）
  function renderGallery() {
    galleryContainer.innerHTML = '';

    const totalPages = Math.ceil(state.commits.length / state.itemsPerPage);
    if (state.currentPage < 1) state.currentPage = 1;
    if (state.currentPage > totalPages) state.currentPage = totalPages;

    const commitIndex = state.currentPage - 1;
    const commit = state.commits[commitIndex];

    if (!commit) return;

    // 建立 Commit Card 容器
    const card = document.createElement('div');
    card.className = 'commit-card';

    // Commit Header: 標題 = commit_message
    const headerHtml = `
      <div class="commit-card-header">
        <div class="commit-title-group">
          <span class="commit-badge">${escapeHtml(commit.short_hash || 'commit')}</span>
          <h2 class="commit-title">${escapeHtml(commit.commit_message || '無 Commit 訊息')}</h2>
        </div>
        <div class="commit-meta">
          <span class="commit-meta-item">👤 ${escapeHtml(commit.author || 'Contributor')}</span>
          <span class="commit-meta-item">🕒 ${escapeHtml(commit.date || '')}</span>
          <span class="commit-meta-item">🖼️ ${commit.photos ? commit.photos.length : 0} 張照片</span>
        </div>
      </div>
    `;

    // Photo Grid
    let gridHtml = '<div class="photo-grid">';
    if (commit.photos && commit.photos.length > 0) {
      commit.photos.forEach((photo, pIdx) => {
        gridHtml += `
          <div class="photo-card" data-commit-idx="${commitIndex}" data-photo-idx="${pIdx}">
            <img 
              src="${escapeHtml(photo.thumbnail_url)}" 
              alt="${escapeHtml(photo.caption || photo.filename)}" 
              loading="lazy"
              onerror="this.onerror=null; this.parentElement.innerHTML='<div class=photo-fallback>🖼️<span>${escapeHtml(photo.filename)}</span></div>';"
            />
            <div class="photo-overlay">
              <span class="photo-caption">${escapeHtml(photo.caption || photo.filename)}</span>
            </div>
          </div>
        `;
      });
    } else {
      gridHtml += '<div style="padding: 2rem; text-align: center; color: var(--text-muted);">此 Commit 未包含照片</div>';
    }
    gridHtml += '</div>';

    card.innerHTML = headerHtml + gridHtml;
    galleryContainer.appendChild(card);

    // 綁定照片點擊事件 (Lightbox)
    const photoCards = card.querySelectorAll('.photo-card');
    photoCards.forEach(card => {
      card.addEventListener('click', () => {
        const cIdx = parseInt(card.getAttribute('data-commit-idx'), 10);
        const pIdx = parseInt(card.getAttribute('data-photo-idx'), 10);
        openLightbox(cIdx, pIdx);
      });
    });
  }

  // 渲染分頁控制器
  function renderPagination() {
    paginationContainer.innerHTML = '';
    const totalPages = state.commits.length;

    if (totalPages <= 1) return;

    // 前一頁
    const prevBtn = document.createElement('button');
    prevBtn.className = 'page-btn';
    prevBtn.innerHTML = '← 上一頁';
    prevBtn.disabled = state.currentPage === 1;
    prevBtn.addEventListener('click', () => {
      if (state.currentPage > 1) {
        state.currentPage--;
        renderGallery();
        renderPagination();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
    paginationContainer.appendChild(prevBtn);

    // 頁號按鈕
    for (let i = 1; i <= totalPages; i++) {
      const pageBtn = document.createElement('button');
      pageBtn.className = `page-btn ${i === state.currentPage ? 'active' : ''}`;
      pageBtn.textContent = `Push ${totalPages - i + 1}`;
      pageBtn.addEventListener('click', () => {
        state.currentPage = i;
        renderGallery();
        renderPagination();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
      paginationContainer.appendChild(pageBtn);
    }

    // 下一頁
    const nextBtn = document.createElement('button');
    nextBtn.className = 'page-btn';
    nextBtn.innerHTML = '下一頁 →';
    nextBtn.disabled = state.currentPage === totalPages;
    nextBtn.addEventListener('click', () => {
      if (state.currentPage < totalPages) {
        state.currentPage++;
        renderGallery();
        renderPagination();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
    paginationContainer.appendChild(nextBtn);
  }

  // Lightbox Modal Controls
  function openLightbox(commitIdx, photoIdx) {
    state.lightbox.isOpen = true;
    state.lightbox.commitIndex = commitIdx;
    state.lightbox.photoIndex = photoIdx;

    updateLightboxContent();
    lightboxModal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeLightbox() {
    state.lightbox.isOpen = false;
    lightboxModal.classList.remove('active');
    document.body.style.overflow = '';
  }

  function updateLightboxContent() {
    const { commitIndex, photoIndex } = state.lightbox;
    const commit = state.commits[commitIndex];
    if (!commit || !commit.photos || !commit.photos[photoIndex]) return;

    const photo = commit.photos[photoIndex];
    lightboxImg.src = photo.photo_url;
    lightboxImg.alt = photo.caption || photo.filename;

    // Fallback for full resolution photo load failure
    lightboxImg.onerror = function() {
      this.src = photo.thumbnail_url;
    };

    lightboxTitle.textContent = photo.caption || photo.filename;
    lightboxSubtext.textContent = `Commit: ${commit.commit_message} (${commit.short_hash}) • ${photoIndex + 1} / ${commit.photos.length}`;
  }

  function navigateLightbox(direction) {
    const { commitIndex, photoIndex } = state.lightbox;
    const commit = state.commits[commitIndex];
    if (!commit || !commit.photos) return;

    let newPhotoIdx = photoIndex + direction;
    if (newPhotoIdx >= 0 && newPhotoIdx < commit.photos.length) {
      state.lightbox.photoIndex = newPhotoIdx;
      updateLightboxContent();
    }
  }

  // Event Listeners for Lightbox
  lightboxClose.addEventListener('click', closeLightbox);
  lightboxPrev.addEventListener('click', () => navigateLightbox(-1));
  lightboxNext.addEventListener('click', () => navigateLightbox(1));

  lightboxModal.addEventListener('click', (e) => {
    if (e.target === lightboxModal || e.target.classList.contains('lightbox-content')) {
      closeLightbox();
    }
  });

  // Keyboard navigation
  document.addEventListener('keydown', (e) => {
    if (!state.lightbox.isOpen) return;

    if (e.key === 'Escape') {
      closeLightbox();
    } else if (e.key === 'ArrowLeft') {
      navigateLightbox(-1);
    } else if (e.key === 'ArrowRight') {
      navigateLightbox(1);
    }
  });

  // Empty & Error states
  function renderEmptyState() {
    galleryContainer.innerHTML = `
      <div style="text-align: center; padding: 4rem 1rem; color: var(--text-secondary);">
        <div style="font-size: 3rem; margin-bottom: 1rem;">📷</div>
        <h2>目前尚無照片</h2>
        <p style="margin-top: 0.5rem; color: var(--text-muted);">請上傳照片至 photos/ 目錄，GitHub Actions 將會自動產出縮圖與相簿！</p>
      </div>
    `;
  }

  function renderErrorState() {
    galleryContainer.innerHTML = `
      <div style="text-align: center; padding: 4rem 1rem; color: var(--text-secondary);">
        <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
        <h2>載入相簿資料失敗</h2>
        <p style="margin-top: 0.5rem; color: var(--text-muted);">請確認 gallery-data.json 檔案是否存在並格式正確。</p>
      </div>
    `;
  }

  // Utility
  function escapeHtml(str) {
    return String(str || '').replace(/[&<>"']/g, match => {
      const escape = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      };
      return escape[match];
    });
  }

  // Launch App
  initTheme();
  loadGalleryData();
});
