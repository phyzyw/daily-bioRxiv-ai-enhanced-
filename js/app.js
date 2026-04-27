let currentDate = '';
let availableDates = [];
let currentView = 'grid';
let currentCategory = 'all';
let paperData = {};
let flatpickrInstance = null;
let isRangeMode = false;
let activeKeywords = [];
let userKeywords = [];
let activeAuthors = [];
let userAuthors = [];
let currentPaperIndex = 0;
let currentFilteredPapers = [];
let dynamicCategories = [];

function loadUserKeywords() {
  const savedKeywords = localStorage.getItem('preferredKeywords');
  if (savedKeywords) {
    try {
      userKeywords = JSON.parse(savedKeywords);
      activeKeywords = [...userKeywords];
    } catch (error) {
      userKeywords = [];
      activeKeywords = [];
    }
  } else {
    userKeywords = [];
    activeKeywords = [];
  }
  renderKeywordTags();
}

function loadUserAuthors() {
  const savedAuthors = localStorage.getItem('preferredAuthors');
  if (savedAuthors) {
    try {
      userAuthors = JSON.parse(savedAuthors);
      activeAuthors = [...userAuthors];
    } catch (error) {
      userAuthors = [];
      activeAuthors = [];
    }
  } else {
    userAuthors = [];
    activeAuthors = [];
  }
  renderAuthorTags();
}

function renderKeywordTags() {
  const keywordTagsElement = document.getElementById('keywordTags');
  const keywordContainer = document.querySelector('.keyword-label-container');
  if (!userKeywords || userKeywords.length === 0) {
    keywordContainer.style.display = 'none';
    return;
  }
  keywordContainer.style.display = 'flex';
  keywordTagsElement.innerHTML = '';
  userKeywords.forEach(keyword => {
    const tagElement = document.createElement('span');
    tagElement.className = `category-button ${activeKeywords.includes(keyword) ? 'active' : ''}`;
    tagElement.dataset.keyword = keyword;
    tagElement.textContent = keyword;
    tagElement.addEventListener('click', () => { toggleKeywordFilter(keyword); });
    keywordTagsElement.appendChild(tagElement);
  });
}

function toggleKeywordFilter(keyword) {
  const index = activeKeywords.indexOf(keyword);
  if (index === -1) { activeKeywords.push(keyword); } else { activeKeywords.splice(index, 1); }
  document.querySelectorAll('[data-keyword]').forEach(tag => {
    if (tag.dataset.keyword === keyword) { tag.classList.toggle('active', activeKeywords.includes(keyword)); }
  });
  renderPapers();
}

function renderAuthorTags() {
  const authorTagsElement = document.getElementById('authorTags');
  const authorContainer = document.querySelector('.author-label-container');
  if (!userAuthors || userAuthors.length === 0) { authorContainer.style.display = 'none'; return; }
  authorContainer.style.display = 'flex';
  authorTagsElement.innerHTML = '';
  userAuthors.forEach(author => {
    const tagElement = document.createElement('span');
    tagElement.className = `category-button ${activeAuthors.includes(author) ? 'active' : ''}`;
    tagElement.dataset.author = author;
    tagElement.textContent = author;
    tagElement.addEventListener('click', () => { toggleAuthorFilter(author); });
    authorTagsElement.appendChild(tagElement);
  });
}

function toggleAuthorFilter(author) {
  const index = activeAuthors.indexOf(author);
  if (index === -1) { activeAuthors.push(author); } else { activeAuthors.splice(index, 1); }
  document.querySelectorAll('[data-author]').forEach(tag => {
    if (tag.dataset.author === author) { tag.classList.toggle('active', activeAuthors.includes(author)); }
  });
  renderPapers();
}

document.addEventListener('DOMContentLoaded', () => {
  initEventListeners();
  loadUserKeywords();
  loadUserAuthors();
  fetchAvailableDates().then(() => {
    if (availableDates.length > 0) { loadPapersByDate(availableDates[0]); }
  });
});

function initEventListeners() {
  document.getElementById('calendarButton').addEventListener('click', (e) => { e.stopPropagation(); toggleDatePicker(); });
  document.querySelector('.date-picker-modal').addEventListener('click', (event) => { if (event.target === event.currentTarget) toggleDatePicker(); });
  document.querySelector('.date-picker-content').addEventListener('click', (e) => e.stopPropagation());
  document.getElementById('dateRangeMode').addEventListener('change', toggleRangeMode);
  document.getElementById('closeModal').addEventListener('click', closeModal);
  document.querySelector('.paper-modal').addEventListener('click', (event) => { if (event.target === event.currentTarget) closeModal(); });
  document.addEventListener('keydown', (event) => {
    const activeElement = document.activeElement;
    const isInputFocused = activeElement && (activeElement.tagName === 'INPUT' || activeElement.tagName === 'TEXTAREA' || activeElement.isContentEditable);
    if (event.key === 'Escape') {
      const paperModal = document.getElementById('paperModal');
      const datePickerModal = document.getElementById('datePickerModal');
      if (paperModal.classList.contains('active')) closeModal();
      else if (datePickerModal.classList.contains('active')) toggleDatePicker();
    } else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      const paperModal = document.getElementById('paperModal');
      if (paperModal.classList.contains('active')) { event.preventDefault(); event.key === 'ArrowLeft' ? navigateToPreviousPaper() : navigateToNextPaper(); }
    } else if (event.key === ' ' || event.key === 'Spacebar') {
      const datePickerModal = document.getElementById('datePickerModal');
      if (!isInputFocused && !datePickerModal.classList.contains('active')) { event.preventDefault(); event.stopPropagation(); showRandomPaper(); }
    }
  });
  const categoryScroll = document.querySelector('.category-scroll');
  if (categoryScroll) { categoryScroll.addEventListener('wheel', function(e) { if (e.deltaY !== 0) { e.preventDefault(); this.scrollLeft += e.deltaY; } }); }
}

async function fetchAvailableDates() {
  try {
    const response = await fetch('assets/file-list.txt');
    if (!response.ok) return [];
    const text = await response.text();
    const files = text.trim().split('\n');
    const dateRegex = /(\d{4}-\d{2}-\d{2})_AI_enhanced_Chinese\.jsonl/;
    const dates = [];
    files.forEach(file => { const match = file.match(dateRegex); if (match && match[1]) dates.push(match[1]); });
    availableDates = [...new Set(dates)];
    availableDates.sort((a, b) => new Date(b) - new Date(a));
    initDatePicker();
    return availableDates;
  } catch (error) { console.error('Failed to fetch available dates:', error); }
}

function initDatePicker() {
  const datepickerInput = document.getElementById('datepicker');
  if (flatpickrInstance) flatpickrInstance.destroy();
  const enabledDatesMap = {};
  availableDates.forEach(date => { enabledDatesMap[date] = true; });
  flatpickrInstance = flatpickr(datepickerInput, {
    inline: true, dateFormat: "Y-m-d", defaultDate: availableDates[0],
    enable: [function(date) { const dateStr = date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, '0') + "-" + String(date.getDate()).padStart(2, '0'); return !!enabledDatesMap[dateStr]; }],
    onChange: function(selectedDates, dateStr) {
      if (isRangeMode && selectedDates.length === 2) { loadPapersByDateRange(formatDateForAPI(selectedDates[0]), formatDateForAPI(selectedDates[1])); toggleDatePicker(); }
      else if (!isRangeMode && selectedDates.length === 1) { const selectedDate = formatDateForAPI(selectedDates[0]); if (availableDates.includes(selectedDate)) { loadPapersByDate(selectedDate); toggleDatePicker(); } }
    }
  });
  const inputElement = document.querySelector('.flatpickr-input');
  if (inputElement) inputElement.style.display = 'none';
}

function formatDateForAPI(date) { return date.getFullYear() + "-" + String(date.getMonth() + 1).padStart(2, '0') + "-" + String(date.getDate()).padStart(2, '0'); }
function toggleRangeMode() { if (flatpickrInstance) flatpickrInstance.set('mode', isRangeMode ? 'range' : 'single'); isRangeMode = document.getElementById('dateRangeMode').checked; }

async function loadPapersByDate(date) {
  currentDate = date;
  document.getElementById('currentDate').textContent = formatDate(date);
  if (flatpickrInstance) flatpickrInstance.setDate(date, false);
  const container = document.getElementById('paperContainer');
  container.innerHTML = '<div class="loading-container"><div class="loading-spinner"></div><p>Loading papers...</p></div>';
  try {
    const response = await fetch(`data/${date}_AI_enhanced_Chinese.jsonl`);
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const text = await response.text();
    paperData = parseJsonlData(text, date);
    updateDynamicCategories();
    renderCategoryFilter();
    renderPapers();
  } catch (error) {
    console.error('Failed to load papers:', error);
    container.innerHTML = `<div class="loading-container"><p>Loading data failed. Please retry.</p><p>Error: ${error.message}</p></div>`;
  }
}

function parseJsonlData(jsonlText, date) {
  const result = {};
  const lines = jsonlText.trim().split('\n');
  lines.forEach(line => {
    try {
      const paper = JSON.parse(line);
      if (!paper.categories) return;
      let allCategories = Array.isArray(paper.categories) ? paper.categories : [paper.categories];
      const primaryCategory = allCategories[0] || 'Uncategorized';
      if (!result[primaryCategory]) result[primaryCategory] = [];
      const summary = paper.AI && paper.AI.tldr ? paper.AI.tldr : paper.summary;
      result[primaryCategory].push({
        title: paper.title,
        url: paper.abs || `https://www.biorxiv.org/content/${paper.id}`,
        authors: Array.isArray(paper.authors) ? paper.authors.join(', ') : paper.authors,
        allCategories: allCategories,
        summary: summary,
        details: paper.summary || '',
        date: date,
        id: paper.id,
        motivation: paper.AI && paper.AI.motivation ? paper.AI.motivation : '',
        method: paper.AI && paper.AI.method ? paper.AI.method : '',
        result: paper.AI && paper.AI.result ? paper.AI.result : '',
        conclusion: paper.AI && paper.AI.conclusion ? paper.AI.conclusion : ''
      });
    } catch (error) { console.error('Failed to parse JSON line:', error, line); }
  });
  return result;
}

function updateDynamicCategories() {
  const cats = new Set();
  Object.keys(paperData).forEach(cat => cats.add(cat));
  dynamicCategories = Array.from(cats).sort();
}

function renderCategoryFilter() {
  const container = document.querySelector('.category-scroll');
  let totalPapers = 0;
  Object.values(paperData).forEach(papers => totalPapers += papers.length);
  const categoryCounts = {};
  dynamicCategories.forEach(cat => { categoryCounts[cat] = paperData[cat] ? paperData[cat].length : 0; });
  container.innerHTML = `<button class="category-button ${currentCategory === 'all' ? 'active' : ''}" data-category="all">All<span class="category-count">${totalPapers}</span></button>`;
  dynamicCategories.forEach(category => {
    const count = categoryCounts[category] || 0;
    const button = document.createElement('button');
    button.className = `category-button ${category === currentCategory ? 'active' : ''}`;
    button.innerHTML = `${category}<span class="category-count">${count}</span>`;
    button.dataset.category = category;
    button.addEventListener('click', () => { filterByCategory(category); });
    container.appendChild(button);
  });
  document.querySelector('.category-button[data-category="all"]').addEventListener('click', () => { filterByCategory('all'); });
}

function filterByCategory(category) {
  currentCategory = category;
  document.querySelectorAll('.category-button').forEach(button => { button.classList.toggle('active', button.dataset.category === category); });
  renderPapers();
}

function highlightMatches(text, terms, className = 'highlight-match') {
  if (!terms || terms.length === 0 || !text) return text;
  let result = text;
  const sortedTerms = [...terms].sort((a, b) => b.length - a.length);
  sortedTerms.forEach(term => { const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'); result = result.replace(regex, `<span class="${className}">$1</span>`); });
  return result;
}

function renderPapers() {
  const container = document.getElementById('paperContainer');
  container.innerHTML = '';
  container.className = `paper-container ${currentView === 'list' ? 'list-view' : ''}`;
  let papers = [];
  if (currentCategory === 'all') {
    const seenIds = new Set();
    dynamicCategories.forEach(category => {
      if (paperData[category]) {
        papers = papers.concat(paperData[category].filter(paper => { if (seenIds.has(paper.id)) return false; seenIds.add(paper.id); return true; }));
      }
    });
  } else if (paperData[currentCategory]) { papers = paperData[currentCategory]; }

  let filteredPapers = [...papers];
  if (activeKeywords.length > 0 || activeAuthors.length > 0) {
    filteredPapers.sort((a, b) => {
      const aMatch = (activeKeywords.length > 0 && activeKeywords.some(kw => `${a.title} ${a.summary}`.toLowerCase().includes(kw.toLowerCase()))) || (activeAuthors.length > 0 && activeAuthors.some(au => a.authors.toLowerCase().includes(au.toLowerCase())));
      const bMatch = (activeKeywords.length > 0 && activeKeywords.some(kw => `${b.title} ${b.summary}`.toLowerCase().includes(kw.toLowerCase()))) || (activeAuthors.length > 0 && activeAuthors.some(au => b.authors.toLowerCase().includes(au.toLowerCase())));
      if (aMatch && !bMatch) return -1; if (!aMatch && bMatch) return 1; return 0;
    });
    filteredPapers.forEach(paper => {
      const matchesKeyword = activeKeywords.length > 0 ? activeKeywords.some(kw => `${paper.title} ${paper.summary}`.toLowerCase().includes(kw.toLowerCase())) : false;
      const matchesAuthor = activeAuthors.length > 0 ? activeAuthors.some(au => paper.authors.toLowerCase().includes(au.toLowerCase())) : false;
      paper.isMatched = matchesKeyword || matchesAuthor;
    });
  }
  currentFilteredPapers = [...filteredPapers];
  if (filteredPapers.length === 0) { container.innerHTML = '<div class="loading-container"><p>No papers found.</p></div>'; return; }

  filteredPapers.forEach((paper, index) => {
    const paperCard = document.createElement('div');
    paperCard.className = `paper-card ${paper.isMatched ? 'matched-paper' : ''}`;
    paperCard.dataset.id = paper.id || paper.url;
    const categoryTags = paper.allCategories ? paper.allCategories.map(cat => `<span class="category-tag">${cat}</span>`).join('') : '';
    const highlightedTitle = activeKeywords.length > 0 ? highlightMatches(paper.title, activeKeywords, 'keyword-highlight') : paper.title;
    const highlightedSummary = activeKeywords.length > 0 ? highlightMatches(paper.summary, activeKeywords, 'keyword-highlight') : paper.summary;
    const highlightedAuthors = activeAuthors.length > 0 ? highlightMatches(paper.authors, activeAuthors, 'author-highlight') : paper.authors;
    paperCard.innerHTML = `
      <div class="paper-card-index">${index + 1}</div>
      ${paper.isMatched ? '<div class="match-badge"></div>' : ''}
      <div class="paper-card-header">
        <h3 class="paper-card-title">${highlightedTitle}</h3>
        <p class="paper-card-authors">${highlightedAuthors}</p>
        <div class="paper-card-categories">${categoryTags}</div>
      </div>
      <div class="paper-card-body">
        <p class="paper-card-summary">${highlightedSummary}</p>
        <div class="paper-card-footer">
          <span class="paper-card-date">${formatDate(paper.date)}</span>
          <span class="paper-card-link">Details</span>
        </div>
      </div>
    `;
    paperCard.addEventListener('click', () => { currentPaperIndex = index; showPaperDetails(paper, index + 1); });
    container.appendChild(paperCard);
  });
}

function showPaperDetails(paper, paperIndex) {
  const modal = document.getElementById('paperModal');
  const modalBody = document.getElementById('modalBody');
  modalBody.scrollTop = 0;
  const highlightedTitle = activeKeywords.length > 0 ? highlightMatches(paper.title, activeKeywords, 'keyword-highlight') : paper.title;
  document.getElementById('modalTitle').innerHTML = paperIndex ? `<span class="paper-index-badge">${paperIndex}</span> ${highlightedTitle}` : highlightedTitle;
  const categoryDisplay = paper.allCategories ? paper.allCategories.join(', ') : '';
  const highlightedAuthors = activeAuthors.length > 0 ? highlightMatches(paper.authors, activeAuthors, 'author-highlight') : paper.authors;
  const highlightedSummary = activeKeywords.length > 0 ? highlightMatches(paper.summary, activeKeywords, 'keyword-highlight') : paper.summary;
  const highlightedMotivation = paper.motivation && activeKeywords.length > 0 ? highlightMatches(paper.motivation, activeKeywords, 'keyword-highlight') : paper.motivation;
  const highlightedMethod = paper.method && activeKeywords.length > 0 ? highlightMatches(paper.method, activeKeywords, 'keyword-highlight') : paper.method;
  const highlightedResult = paper.result && activeKeywords.length > 0 ? highlightMatches(paper.result, activeKeywords, 'keyword-highlight') : paper.result;
  const highlightedConclusion = paper.conclusion && activeKeywords.length > 0 ? highlightMatches(paper.conclusion, activeKeywords, 'keyword-highlight') : paper.conclusion;
  const matchedPaperClass = paper.isMatched ? 'matched-paper-details' : '';
  const modalContent = `
    <div class="paper-details ${matchedPaperClass}">
      <p><strong>Authors: </strong>${highlightedAuthors}</p>
      <p><strong>Categories: </strong>${categoryDisplay}</p>
      <p><strong>Date: </strong>${formatDate(paper.date)}</p>
      <h3>简要摘要</h3>
      <p>${highlightedSummary}</p>
      <div class="paper-sections">
        ${paper.motivation ? `<div class="paper-section"><h4>研究动机</h4><p>${highlightedMotivation}</p></div>` : ''}
        ${paper.method ? `<div class="paper-section"><h4>研究方法</h4><p>${highlightedMethod}</p></div>` : ''}
        ${paper.result ? `<div class="paper-section"><h4>主要结果</h4><p>${highlightedResult}</p></div>` : ''}
        ${paper.conclusion ? `<div class="paper-section"><h4>结论与意义</h4><p>${highlightedConclusion}</p></div>` : ''}
      </div>
      ${paper.details ? `<h3>原始摘要</h3><p class="original-abstract">${paper.details}</p>` : ''}
    </div>
  `;
  document.getElementById('modalBody').innerHTML = modalContent;
  document.getElementById('paperLink').href = paper.url;
  document.getElementById('pdfLink').href = paper.url + '.full.pdf';
  const paperPosition = document.getElementById('paperPosition');
  if (paperPosition && currentFilteredPapers.length > 0) { paperPosition.textContent = `${currentPaperIndex + 1} / ${currentFilteredPapers.length}`; }
  modal.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeModal() {
  document.getElementById('modalBody').scrollTop = 0;
  document.getElementById('paperModal').classList.remove('active');
  document.body.style.overflow = '';
}

function navigateToPreviousPaper() {
  if (currentFilteredPapers.length === 0) return;
  currentPaperIndex = currentPaperIndex > 0 ? currentPaperIndex - 1 : currentFilteredPapers.length - 1;
  showPaperDetails(currentFilteredPapers[currentPaperIndex], currentPaperIndex + 1);
}

function navigateToNextPaper() {
  if (currentFilteredPapers.length === 0) return;
  currentPaperIndex = currentPaperIndex < currentFilteredPapers.length - 1 ? currentPaperIndex + 1 : 0;
  showPaperDetails(currentFilteredPapers[currentPaperIndex], currentPaperIndex + 1);
}

function showRandomPaper() {
  if (currentFilteredPapers.length === 0) return;
  const randomIndex = Math.floor(Math.random() * currentFilteredPapers.length);
  currentPaperIndex = randomIndex;
  showPaperDetails(currentFilteredPapers[randomIndex], currentPaperIndex + 1);
}

function toggleDatePicker() {
  const datePicker = document.getElementById('datePickerModal');
  datePicker.classList.toggle('active');
  if (datePicker.classList.contains('active')) { document.body.style.overflow = 'hidden'; if (flatpickrInstance) flatpickrInstance.setDate(currentDate, false); }
  else { document.body.style.overflow = ''; }
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'numeric', day: 'numeric' });
}

async function loadPapersByDateRange(startDate, endDate) {
  const validDatesInRange = availableDates.filter(date => date >= startDate && date <= endDate);
  if (validDatesInRange.length === 0) { alert('No available papers in the selected date range.'); return; }
  currentDate = `${startDate} to ${endDate}`;
  document.getElementById('currentDate').textContent = `${formatDate(startDate)} - ${formatDate(endDate)}`;
  const container = document.getElementById('paperContainer');
  container.innerHTML = '<div class="loading-container"><div class="loading-spinner"></div><p>Loading papers...</p></div>';
  try {
    const allPaperData = {};
    for (const date of validDatesInRange) {
      const response = await fetch(`data/${date}_AI_enhanced_Chinese.jsonl`);
      const text = await response.text();
      const dataPapers = parseJsonlData(text, date);
      Object.keys(dataPapers).forEach(category => { if (!allPaperData[category]) allPaperData[category] = []; allPaperData[category] = allPaperData[category].concat(dataPapers[category]); });
    }
    paperData = allPaperData;
    updateDynamicCategories();
    renderCategoryFilter();
    renderPapers();
  } catch (error) {
    console.error('Failed to load papers:', error);
    container.innerHTML = `<div class="loading-container"><p>Loading failed. Error: ${error.message}</p></div>`;
  }
}
