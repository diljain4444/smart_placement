import { useState, useEffect } from 'react'
import { fetchNews, refreshNews } from '../api'

// Company logo/icon mapping — first letter as fallback
const COMPANY_COLORS = {
  Google: '#4285F4',
  Microsoft: '#00A4EF',
  Amazon: '#FF9900',
  Meta: '#0668E1',
  Apple: '#A2AAAD',
  Nvidia: '#76B900',
  OpenAI: '#10A37F',
  Anthropic: '#D4A574',
  TCS: '#0066B3',
  Infosys: '#007CC3',
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    if (isNaN(d.getTime())) return dateStr
    return d.toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    })
  } catch {
    return dateStr
  }
}

export default function LatestNews() {
  const [newsData, setNewsData] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [fetchedAt, setFetchedAt] = useState('')

  const loadNews = async (forceRefresh = false) => {
    try {
      if (forceRefresh) setRefreshing(true)
      else setLoading(true)
      setError('')

      const res = forceRefresh ? await refreshNews() : await fetchNews()
      setNewsData(res.data.results || [])
      setFetchedAt(res.data.fetched_at || '')
    } catch (err) {
      console.error('News fetch failed:', err)
      setError('Failed to load news. Please try again later.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadNews()
  }, [])

  // Count total news items
  const totalNews = newsData.reduce((sum, c) => sum + (c.news?.length || 0), 0)

  return (
    <div className="news-page">
      <div className="page-header">
        <h1>Latest News</h1>
        <p>Placement-relevant news from top companies, curated by AI</p>
      </div>

      {/* Toolbar */}
      <div className="news-toolbar">
        <div className="news-stats">
          <span className="news-stat-badge">
            {newsData.length} Companies
          </span>
          <span className="news-stat-badge">
            {totalNews} Articles
          </span>
          {fetchedAt && (
            <span className="news-fetched-at">
              Updated {formatDate(fetchedAt)}
            </span>
          )}
        </div>
        <button
          className="news-refresh-btn"
          onClick={() => loadNews(true)}
          disabled={refreshing || loading}
        >
          {refreshing ? '↻ Refreshing…' : '↻ Refresh'}
        </button>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner" />
          <span className="loading-message">Fetching latest news…</span>
        </div>
      )}

      {/* Error state */}
      {error && <div className="error-message">{error}</div>}

      {/* News content */}
      {!loading && !error && (
        <div className="news-grid">
          {newsData.map((company) => {
            const color = COMPANY_COLORS[company.company] || 'var(--accent)'
            const hasNews = company.news && company.news.length > 0

            return (
              <div className="news-company-card" key={company.company}>
                {/* Company header */}
                <div className="news-company-header">
                  <div
                    className="news-company-icon"
                    style={{ background: color }}
                  >
                    {company.company.charAt(0)}
                  </div>
                  <div className="news-company-info">
                    <h3 className="news-company-name">{company.company}</h3>
                    <span className="news-company-count">
                      {hasNews
                        ? `${company.news.length} article${company.news.length > 1 ? 's' : ''}`
                        : 'No recent news'}
                    </span>
                  </div>
                  {company.stale && (
                    <span className="news-stale-badge">Cached</span>
                  )}
                  {company.error && (
                    <span className="news-error-badge">Error</span>
                  )}
                </div>

                {/* News items */}
                {hasNews ? (
                  <div className="news-items">
                    {company.news.map((item, idx) => (
                      <div className="news-item" key={idx}>
                        <div className="news-headline">{item.headline}</div>
                        <div className="news-date">
                          {formatDate(item.published_date)}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="news-empty">
                    <span className="news-empty-icon">📭</span>
                    <span>No placement-relevant news in the last 3 days</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
