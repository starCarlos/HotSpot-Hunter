-- HotSpotHunter 数据库表结构

-- ============================================
-- 平台信息表
-- 核心：id 不变，name 可变
-- type: 平台类型 (forum=论坛, news=新闻网站)
-- ============================================
CREATE TABLE IF NOT EXISTS platforms (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT DEFAULT 'news' CHECK(type IN ('forum', 'news')),
    is_active INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 新闻条目表
-- 以 URL + platform_id 为唯一标识，支持去重存储
-- ============================================
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    normalized_title TEXT DEFAULT '',     -- 标准化标题（去除空格和符号，用于去重）
    platform_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    url TEXT DEFAULT '',
    mobile_url TEXT DEFAULT '',
    first_crawl_time INTEGER NOT NULL,   -- 首次抓取时间（Unix 时间戳）
    last_crawl_time INTEGER NOT NULL,    -- 最后抓取时间（Unix 时间戳）
    crawl_count INTEGER DEFAULT 1,       -- 抓取次数
    importance TEXT DEFAULT '',           -- AI分析的重要性评级: 'critical'|'high'|'medium'|'low'
    has_been_pushed INTEGER DEFAULT 0,    -- 是否已推送过（0=未推送，1=已推送）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (platform_id) REFERENCES platforms(id)
);

-- ============================================
-- 排名历史表
-- 记录每次抓取时的排名变化
-- ============================================
CREATE TABLE IF NOT EXISTS rank_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_item_id INTEGER NOT NULL,
    rank INTEGER NOT NULL,
    crawl_time INTEGER NOT NULL,         -- 抓取时间（Unix 时间戳）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (news_item_id) REFERENCES news_items(id)
);

-- ============================================
-- 抓取记录表
-- 记录每次抓取的时间和数量
-- ============================================
CREATE TABLE IF NOT EXISTS crawl_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    crawl_time INTEGER NOT NULL UNIQUE,  -- 抓取时间（Unix 时间戳）
    total_items INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 抓取来源状态表
-- 记录每次抓取各平台的成功/失败状态
-- ============================================
CREATE TABLE IF NOT EXISTS crawl_source_status (
    crawl_record_id INTEGER NOT NULL,
    platform_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('success', 'failed')),
    PRIMARY KEY (crawl_record_id, platform_id),
    FOREIGN KEY (crawl_record_id) REFERENCES crawl_records(id),
    FOREIGN KEY (platform_id) REFERENCES platforms(id)
);

-- ============================================
-- 索引定义
-- ============================================

-- 平台索引
CREATE INDEX IF NOT EXISTS idx_news_platform ON news_items(platform_id);

-- 时间索引（用于查询最新数据）
CREATE INDEX IF NOT EXISTS idx_news_crawl_time ON news_items(last_crawl_time);

-- 标题索引（用于标题搜索）
CREATE INDEX IF NOT EXISTS idx_news_title ON news_items(title);

-- URL + platform_id 唯一索引（仅对非空 URL，实现去重）
CREATE UNIQUE INDEX IF NOT EXISTS idx_news_url_platform
    ON news_items(url, platform_id) WHERE url != '';

-- 抓取状态索引
CREATE INDEX IF NOT EXISTS idx_crawl_status_record ON crawl_source_status(crawl_record_id);

-- 排名历史索引
CREATE INDEX IF NOT EXISTS idx_rank_history_news ON rank_history(news_item_id);
