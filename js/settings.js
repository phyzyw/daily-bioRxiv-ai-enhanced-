document.addEventListener('DOMContentLoaded', () => {
  initSettings();
  initEventListeners();
});

function initSettings() {
  loadKeywordPreferences();
  loadAuthorPreferences();
}

function loadKeywordPreferences() {
  const container = document.getElementById('selectedKeywords');
  container.innerHTML = '';
  let saved = localStorage.getItem('preferredKeywords');
  let keywords = [];
  if (saved) { try { keywords = JSON.parse(saved); } catch (e) {} }
  if (keywords.length > 0) { keywords.forEach(kw => addKeywordTag(kw)); } else { showEmptyTagMessage(); }
}

function loadAuthorPreferences() {
  const container = document.getElementById('selectedAuthors');
  container.innerHTML = '';
  let saved = localStorage.getItem('preferredAuthors');
  let authors = [];
  if (saved) { try { authors = JSON.parse(saved); } catch (e) {} }
  if (authors.length > 0) { authors.forEach(au => addAuthorTag(au)); } else { showEmptyAuthorMessage(); }
}

function showEmptyTagMessage() {
  const c = document.getElementById('selectedKeywords');
  const m = document.createElement('div'); m.id = 'emptyTagMessage'; m.className = 'empty-tag-message';
  m.textContent = 'No keywords added yet. Add some keywords below.'; c.appendChild(m);
}

function showEmptyAuthorMessage() {
  const c = document.getElementById('selectedAuthors');
  const m = document.createElement('div'); m.id = 'emptyAuthorMessage'; m.className = 'empty-tag-message';
  m.textContent = 'No authors added yet. Add some authors below.'; c.appendChild(m);
}

function hideEmptyTagMessage() { const m = document.getElementById('emptyTagMessage'); if (m) m.remove(); }
function hideEmptyAuthorMessage() { const m = document.getElementById('emptyAuthorMessage'); if (m) m.remove(); }

function addKeywordTag(keyword) {
  const container = document.getElementById('selectedKeywords');
  hideEmptyTagMessage();
  const existing = container.querySelectorAll('.category-button');
  for (let i = 0; i < existing.length; i++) {
    if (existing[i].textContent.trim().startsWith(keyword)) { existing[i].classList.add('tag-highlight'); setTimeout(() => existing[i].classList.remove('tag-highlight'), 1000); return; }
  }
  const tag = document.createElement('span');
  tag.className = 'category-button tag-appear';
  tag.innerHTML = `${keyword} <button class="remove-tag">×</button>`;
  tag.querySelector('.remove-tag').addEventListener('click', (e) => {
    e.preventDefault(); e.stopPropagation(); tag.classList.add('tag-disappear');
    setTimeout(() => { tag.remove(); if (container.querySelectorAll('.category-button').length === 0) showEmptyTagMessage(); }, 300);
  });
  container.appendChild(tag);
  setTimeout(() => tag.classList.remove('tag-appear'), 300);
}

function addAuthorTag(author) {
  const container = document.getElementById('selectedAuthors');
  hideEmptyAuthorMessage();
  const existing = container.querySelectorAll('.category-button');
  for (let i = 0; i < existing.length; i++) {
    if (existing[i].textContent.trim().startsWith(author)) { existing[i].classList.add('tag-highlight'); setTimeout(() => existing[i].classList.remove('tag-highlight'), 1000); return; }
  }
  const tag = document.createElement('span');
  tag.className = 'category-button tag-appear';
  tag.innerHTML = `${author} <button class="remove-tag">×</button>`;
  tag.querySelector('.remove-tag').addEventListener('click', (e) => {
    e.preventDefault(); e.stopPropagation(); tag.classList.add('tag-disappear');
    setTimeout(() => { tag.remove(); if (container.querySelectorAll('.category-button').length === 0) showEmptyAuthorMessage(); }, 300);
  });
  container.appendChild(tag);
  setTimeout(() => tag.classList.remove('tag-appear'), 300);
}

function initEventListeners() {
  document.getElementById('addKeyword').addEventListener('click', () => {
    const input = document.getElementById('keywordInput'); const val = input.value.trim();
    if (val) { addKeywordTag(val); input.value = ''; }
  });
  document.getElementById('keywordInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); const val = e.target.value.trim(); if (val) { addKeywordTag(val); e.target.value = ''; } }
  });
  document.getElementById('addAuthor').addEventListener('click', () => {
    const input = document.getElementById('authorInput'); const val = input.value.trim();
    if (val) { addAuthorTag(val); input.value = ''; }
  });
  document.getElementById('authorInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') { e.preventDefault(); const val = e.target.value.trim(); if (val) { addAuthorTag(val); e.target.value = ''; } }
  });
  document.getElementById('saveSettings').addEventListener('click', saveSettings);
  document.getElementById('resetSettings').addEventListener('click', resetSettings);
}

function saveSettings() {
  const kwTags = document.getElementById('selectedKeywords').querySelectorAll('.category-button');
  const keywords = []; kwTags.forEach(tag => keywords.push(tag.textContent.trim().replace('×', '').trim()));
  const auTags = document.getElementById('selectedAuthors').querySelectorAll('.category-button');
  const authors = []; auTags.forEach(tag => authors.push(tag.textContent.trim().replace('×', '').trim()));
  localStorage.setItem('preferredKeywords', JSON.stringify(keywords));
  localStorage.setItem('preferredAuthors', JSON.stringify(authors));
  showNotification('Settings saved successfully!', 'success');
}

function resetSettings() {
  document.getElementById('selectedKeywords').innerHTML = '';
  document.getElementById('selectedAuthors').innerHTML = '';
  showEmptyTagMessage(); showEmptyAuthorMessage();
  showNotification('Settings reset to default!', 'info');
}

function showNotification(message, type = 'success') {
  let notification = document.querySelector('.settings-notification');
  if (!notification) { notification = document.createElement('div'); notification.className = 'settings-notification'; document.body.appendChild(notification); }
  let icon = '';
  let bgColor = 'var(--primary-color)';
  if (type === 'success') { icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z" fill="currentColor"/></svg>'; }
  else { icon = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 15c-.55 0-1-.45-1-1v-4c0-.55.45-1 1-1s1 .45 1 1v4c0 .55-.45 1-1 1zm1-8h-2V7h2v2z" fill="currentColor"/></svg>'; bgColor = '#3b82f6'; }
  notification.innerHTML = `${icon}<span>${message}</span>`;
  notification.style.cssText = 'display:flex;align-items:center;gap:8px;position:fixed;bottom:20px;right:20px;background-color:' + bgColor + ';color:white;padding:12px 20px;border-radius:8px;box-shadow:0 4px 15px rgba(0,0,0,0.15);z-index:1000;opacity:0;transform:translateY(20px);transition:opacity 0.3s ease,transform 0.3s ease;';
  setTimeout(() => { notification.style.opacity = '1'; notification.style.transform = 'translateY(0)'; }, 10);
  setTimeout(() => { notification.style.opacity = '0'; notification.style.transform = 'translateY(20px)'; setTimeout(() => { if (notification.parentNode) notification.parentNode.removeChild(notification); }, 300); }, 3000);
}
