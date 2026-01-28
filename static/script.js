// API 基础 URL
const API_BASE = '/api/filtered-news';

// 状态管理
let startDate = '';
let endDate = '';
let currentCategory = '';
let currentKeyword = '';
let currentImportance = '';
let allNews = [];
let keywords = []; // 所有关键词列表（不随筛选变化）
let allKeywords = []; // 保存所有关键词，用于在切换筛选时恢复
let importanceStats = {};
let savedKeyword = ''; // 保存切换重要性时之前选中的关键词

// 获取本月第一天和今天的日期
function getCurrentMonthRange() {
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth();
    const firstDay = new Date(year, month, 1);
    const today = new Date();
    
    return {
        start: firstDay.toISOString().split('T')[0],
        end: today.toISOString().split('T')[0]
    };
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initDatePicker();
    initFilters();
    initRefreshBtn();
    loadNews();
});

// 初始化日期选择器
function initDatePicker() {
    const startDateInput = document.getElementById('startDate');
    const endDateInput = document.getElementById('endDate');
    
    // 设置默认值：本月1号到今天
    const monthRange = getCurrentMonthRange();
    startDate = monthRange.start;
    endDate = monthRange.end;
    
    startDateInput.value = startDate;
    endDateInput.value = endDate;
    
    // 设置最大日期为今天
    const today = new Date().toISOString().split('T')[0];
    startDateInput.max = today;
    endDateInput.max = today;
    
    // 开始日期变化时，限制结束日期范围
    startDateInput.addEventListener('change', (e) => {
        const selectedStart = e.target.value;
        if (!selectedStart) return;
        
        // 获取选中日期的月份
        const startDateObj = new Date(selectedStart);
        const year = startDateObj.getFullYear();
        const month = startDateObj.getMonth();
        
        // 计算该月的第一天和最后一天
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const todayObj = new Date();
        
        // 结束日期不能早于开始日期，不能晚于该月最后一天或今天（取较小值）
        const maxEndDate = lastDay > todayObj ? todayObj : lastDay;
        const minEndDate = firstDay > new Date(selectedStart) ? firstDay : new Date(selectedStart);
        
        endDateInput.min = minEndDate.toISOString().split('T')[0];
        endDateInput.max = maxEndDate.toISOString().split('T')[0];
        
        // 如果当前结束日期不在范围内，自动调整
        const currentEnd = new Date(endDateInput.value);
        if (currentEnd < minEndDate || currentEnd > maxEndDate) {
            endDateInput.value = maxEndDate.toISOString().split('T')[0];
        }
        
        startDate = selectedStart;
        endDate = endDateInput.value;
        loadNews();
    });
    
    // 结束日期变化时，限制开始日期范围
    endDateInput.addEventListener('change', (e) => {
        const selectedEnd = e.target.value;
        if (!selectedEnd) return;
        
        // 获取选中日期的月份
        const endDateObj = new Date(selectedEnd);
        const year = endDateObj.getFullYear();
        const month = endDateObj.getMonth();
        
        // 计算该月的第一天
        const firstDay = new Date(year, month, 1);
        const todayObj = new Date();
        
        // 开始日期不能晚于结束日期，不能早于该月第一天
        const minStartDate = firstDay;
        const maxStartDate = endDateObj > todayObj ? todayObj : endDateObj;
        
        startDateInput.min = minStartDate.toISOString().split('T')[0];
        startDateInput.max = maxStartDate.toISOString().split('T')[0];
        
        // 如果当前开始日期不在范围内，自动调整
        const currentStart = new Date(startDateInput.value);
        if (currentStart < minStartDate || currentStart > maxStartDate) {
            startDateInput.value = minStartDate.toISOString().split('T')[0];
        }
        
        startDate = startDateInput.value;
        endDate = selectedEnd;
        loadNews();
    });
}

// 初始化筛选器
function initFilters() {
    console.log('[前端] 初始化筛选器...');
    
    // 分类筛选
    const categoryButtons = document.querySelectorAll('[data-category]');
    console.log('[前端] 找到分类按钮:', categoryButtons.length);
    categoryButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('[data-category]').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentCategory = e.target.dataset.category || '';
            filterNews();
        });
    });

    // 关键词筛选
    const keywordButtons = document.querySelectorAll('[data-keyword]');
    console.log('[前端] 找到关键词按钮:', keywordButtons.length);
    keywordButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('[data-keyword]').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentKeyword = e.target.dataset.keyword || '';
            filterNews();
        });
    });

    // 重要性筛选
    const importanceButtons = document.querySelectorAll('[data-importance]');
    console.log('[前端] 找到重要性按钮:', importanceButtons.length);
    importanceButtons.forEach((btn, index) => {
        const importanceValue = btn.dataset.importance || '';
        console.log(`[前端] 按钮 ${index}: ${importanceValue}, 元素:`, btn);
        
        btn.addEventListener('click', (e) => {
            console.log('[前端] 重要性按钮被点击!', e);
            e.preventDefault();
            e.stopPropagation();
            
            // 使用 currentTarget 确保获取到正确的按钮元素（即使点击的是按钮内的文本或 emoji）
            const clickedBtn = e.currentTarget;
            console.log('[前端] 点击的按钮:', clickedBtn, '重要性值:', clickedBtn.dataset.importance);
            
            document.querySelectorAll('[data-importance]').forEach(b => b.classList.remove('active'));
            clickedBtn.classList.add('active');
            currentImportance = clickedBtn.dataset.importance || '';
            
            console.log('[前端] 重要性筛选:', currentImportance);
            // 切换重要性时，保存之前选中的关键词，然后获取所有数据（不传关键词参数）
            // 这样关键词按钮会显示所有关键词，而不是只显示当前筛选结果中的关键词
            savedKeyword = currentKeyword; // 保存之前选中的关键词
            currentKeyword = ''; // 临时清除关键词，以便获取所有数据
            loadNews();
        });
    });
    
    console.log('[前端] 筛选器初始化完成');
}

// 初始化刷新按钮
function initRefreshBtn() {
    document.getElementById('refreshBtn').addEventListener('click', () => {
        loadNews();
    });
}

// 加载新闻
async function loadNews() {
    const newsList = document.getElementById('newsList');
    newsList.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const params = new URLSearchParams();
        
        // 添加日期范围参数
        if (startDate) {
            params.append('start_date', startDate);
        }
        if (endDate) {
            params.append('end_date', endDate);
        }

        // 添加筛选参数
        if (currentCategory) {
            params.append('category', currentCategory);
        }
        if (currentKeyword) {
            params.append('keyword', currentKeyword);
        }
        if (currentImportance) {
            // 处理未评级的情况
            if (currentImportance === 'unrated') {
                // 未评级的情况需要在客户端筛选，不传参数
                console.log('[前端] 未评级筛选，将在客户端处理');
            } else {
                params.append('importance', currentImportance);
                console.log('[前端] 重要性筛选参数:', currentImportance);
            }
        }

        console.log('[前端] API 请求 URL:', `${API_BASE}/filtered?${params}`);
        const response = await fetch(`${API_BASE}/filtered?${params}`);
        const data = await response.json();

        if (data.items) {
            allNews = data.items;
            const newKeywords = data.keywords || [];
            
            // 如果这是第一次加载，或者没有传关键词参数（获取所有数据），保存所有关键词
            if (allKeywords.length === 0 || !params.has('keyword')) {
                allKeywords = newKeywords;
            }
            
            // 使用保存的所有关键词，而不是当前筛选结果的关键词
            keywords = allKeywords.length > 0 ? allKeywords : newKeywords;
            importanceStats = data.importance_stats || {};
            
            // 如果选择未评级，在客户端筛选
            if (currentImportance === 'unrated') {
                allNews = allNews.filter(item => !item.importance || item.importance === '');
            }
            
            updateKeywords();
            updateStats(data);
            
            // 如果之前有保存的关键词，恢复它并在客户端筛选
            if (savedKeyword) {
                currentKeyword = savedKeyword;
                savedKeyword = ''; // 清除保存的关键词
                filterNews(); // 重新应用关键词筛选
            } else {
                filterNews();
            }
        } else {
            newsList.innerHTML = '<div class="empty"><div class="empty-icon">📰</div><div>暂无数据</div></div>';
        }
    } catch (error) {
        console.error('加载新闻失败:', error);
        newsList.innerHTML = '<div class="empty"><div class="empty-icon">❌</div><div>加载失败，请稍后重试</div></div>';
    }
}

// 更新关键词标签
function updateKeywords() {
    const keywordTags = document.getElementById('keywordTags');
    
    // 确定要恢复的关键词（优先使用 savedKeyword，否则使用 currentKeyword）
    const selectedKeyword = savedKeyword || currentKeyword;
    
    keywordTags.innerHTML = '';

    // 优先使用保存的所有关键词，如果为空则从 allNews 中统计
    let keywordsToShow = keywords;
    if (keywordsToShow.length === 0 && allNews.length > 0) {
        // 从所有新闻中统计关键词
        const keywordCounts = {};
        allNews.forEach(item => {
            const keyword = item.keyword || '未分类';
            keywordCounts[keyword] = (keywordCounts[keyword] || 0) + 1;
        });
        keywordsToShow = Object.entries(keywordCounts).map(([name, count]) => ({ name, count }));
        keywordsToShow.sort((a, b) => b.count - a.count); // 按数量排序
    }

    keywordsToShow.forEach(kw => {
        const btn = document.createElement('button');
        btn.className = 'filter-btn';
        btn.dataset.keyword = kw.name;
        btn.textContent = `${kw.name} (${kw.count})`;
        
        // 如果这个关键词是之前选中的，恢复选中状态
        if (selectedKeyword && kw.name === selectedKeyword) {
            btn.classList.add('active');
        }
        
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('[data-keyword]').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentKeyword = e.target.dataset.keyword || '';
            savedKeyword = ''; // 清除保存的关键词
            filterNews();
        });
        keywordTags.appendChild(btn);
    });
}

// 根据当前筛选结果更新关键词数量
function updateKeywordsCount(filteredNews) {
    // 统计当前筛选结果中每个关键词的数量
    const keywordCounts = {};
    filteredNews.forEach(item => {
        const keyword = item.keyword || '未分类';
        keywordCounts[keyword] = (keywordCounts[keyword] || 0) + 1;
    });

    // 更新关键词标签的数量显示
    document.querySelectorAll('[data-keyword]').forEach(btn => {
        const keyword = btn.dataset.keyword || '';
        let count = 0;
        let keywordName = '';
        
        if (keyword === '') {
            // "全部"按钮，显示当前筛选结果的总数
            count = filteredNews.length;
            keywordName = '全部';
        } else {
            // 其他关键词按钮
            count = keywordCounts[keyword] || 0;
            const kwObj = keywords.find(kw => kw.name === keyword);
            keywordName = kwObj ? kwObj.name : keyword;
        }
        
        // 更新按钮文本
        btn.textContent = `${keywordName} (${count})`;
    });
}

// 更新统计信息
function updateStats(data) {
    const totalCount = document.getElementById('totalCount');
    const categoryStats = document.getElementById('categoryStats');
    const importanceStatsEl = document.getElementById('importanceStats');
    
    // 如果选择了重要性筛选，显示筛选后的数量，否则显示总数
    const displayCount = currentImportance === 'unrated' 
        ? allNews.filter(item => !item.importance || item.importance === '').length
        : (data.total_count || 0);
    totalCount.textContent = `共 ${displayCount} 条`;
    
    if (data.categories) {
        const stats = [];
        if (data.categories.forum > 0) {
            stats.push(`论坛 ${data.categories.forum} 条`);
        }
        if (data.categories.news > 0) {
            stats.push(`新闻 ${data.categories.news} 条`);
        }
        categoryStats.textContent = stats.join(' | ');
    }
    
    // 显示重要性统计
    if (data.importance_stats) {
        const importanceStats = data.importance_stats;
        const stats = [];
        if (importanceStats.critical > 0) {
            stats.push(`🔴 关键 ${importanceStats.critical}`);
        }
        if (importanceStats.high > 0) {
            stats.push(`🟠 重要 ${importanceStats.high}`);
        }
        if (importanceStats.medium > 0) {
            stats.push(`🟡 中等 ${importanceStats.medium}`);
        }
        if (importanceStats.low > 0) {
            stats.push(`⚪ 一般 ${importanceStats.low}`);
        }
        if (importanceStats.unrated > 0) {
            stats.push(`未评级 ${importanceStats.unrated}`);
        }
        importanceStatsEl.textContent = stats.join(' | ');
    } else {
        importanceStatsEl.textContent = '';
    }
}

// 筛选新闻
function filterNews() {
    let filtered = [...allNews];

    // 分类筛选
    if (currentCategory) {
        filtered = filtered.filter(item => item.category === currentCategory);
    }

    // 根据当前分类筛选结果更新关键词数量（不包含关键词筛选）
    updateKeywordsCount(filtered);

    // 关键词筛选（在更新数量之后）
    if (currentKeyword) {
        filtered = filtered.filter(item => item.keyword === currentKeyword);
    }
    
    // 重要性筛选（如果选择未评级，已在 loadNews 中处理）
    // 这里只处理其他重要性级别的客户端筛选（如果需要）
    
    renderNews(filtered);
}

// 渲染新闻列表
function renderNews(news) {
    const newsList = document.getElementById('newsList');
    
    if (news.length === 0) {
        newsList.innerHTML = '<div class="empty"><div class="empty-icon">📭</div><div>暂无匹配的新闻</div></div>';
        return;
    }

    newsList.innerHTML = news.map(item => {
        const rankClass = item.rank <= 5 ? 'hot' : '';
        const timeStr = formatTime(item.last_time);
        
        // 重要性图标
        let importanceIcon = '';
        if (item.importance) {
            const importanceLabels = {
                'critical': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '⚪'
            };
            const icon = importanceLabels[item.importance] || '';
            if (icon) {
                importanceIcon = `<span class="importance-icon ${item.importance}" title="重要性: ${getImportanceLabel(item.importance)}">${icon}</span>`;
            }
        }
        
        return `
            <div class="news-item">
                <div class="news-header">
                    <div style="display: flex; align-items: center; flex: 1;">
                        ${importanceIcon}
                        <a href="${item.url || '#'}" target="_blank" class="news-title">${escapeHtml(item.title)}</a>
                    </div>
                    <span class="rank-badge ${rankClass}">#${item.rank}</span>
                </div>
                <div class="news-meta">
                    <div class="news-tags">
                        <span class="tag keyword-tag">${escapeHtml(item.keyword)}</span>
                        <span class="tag category-tag">${item.category === 'forum' ? '论坛' : '新闻'}</span>
                        <span class="tag platform-tag">${escapeHtml(item.platform_name)}</span>
                    </div>
                    <span>${timeStr}</span>
                </div>
            </div>
        `;
    }).join('');
}

// 格式化时间（将 Unix 时间戳转换为 YYYY-MM-DD HH:MM:SS 格式）
function formatTime(timeStr) {
    if (!timeStr) return '';
    
    // 如果是 Unix 时间戳（数字字符串）
    const timestamp = parseInt(timeStr);
    if (!isNaN(timestamp) && timestamp > 0) {
        const date = new Date(timestamp * 1000); // Unix 时间戳是秒，需要乘以 1000
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }
    
    // 处理 HH-MM 格式（向后兼容）
    if (timeStr.includes('-') && timeStr.length === 5) {
        return timeStr.replace('-', ':');
    }
    
    // 处理其他格式
    return timeStr;
}

// HTML 转义
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// 获取重要性标签文本
function getImportanceLabel(importance) {
    const labels = {
        'critical': '关键',
        'high': '重要',
        'medium': '中等',
        'low': '一般'
    };
    return labels[importance] || importance;
}

// 主题切换功能
function initTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const savedTheme = localStorage.getItem('theme') || 'light';
    
    // 应用保存的主题
    applyTheme(savedTheme);
    
    // 绑定切换事件
    themeToggle.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        applyTheme(newTheme);
        localStorage.setItem('theme', newTheme);
    });
}

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    const themeToggle = document.getElementById('themeToggle');
    
    // 更新按钮图标
    if (theme === 'dark') {
        themeToggle.textContent = '☀️';
        themeToggle.title = '切换到浅色主题';
    } else {
        themeToggle.textContent = '🌙';
        themeToggle.title = '切换到深色主题';
    }
}
