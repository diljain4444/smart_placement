export default function ResourceFilters({ resources, filters, onFilterChange }) {
  // Dynamically extract unique values from the actual data
  const categories = ['All', ...new Set(resources.map(r => r.category).filter(Boolean).sort())]
  const languages = ['All', ...new Set(resources.map(r => r.language).filter(Boolean).sort())]
  const levels = ['All Levels', ...new Set(resources.map(r => r.level).filter(Boolean).sort())]

  return (
    <div className="li-filters">
      <div className="li-filter-group">
        <span className="li-filter-label">Category</span>
        <div className="li-filter-pills">
          {categories.map(cat => (
            <button
              key={cat}
              className={`li-filter-pill ${filters.category === cat ? 'active' : ''}`}
              onClick={() => onFilterChange('category', cat)}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {languages.length > 2 && (
        <div className="li-filter-group">
          <span className="li-filter-label">Language</span>
          <div className="li-filter-pills">
            {languages.map(lang => (
              <button
                key={lang}
                className={`li-filter-pill ${filters.language === lang ? 'active' : ''}`}
                onClick={() => onFilterChange('language', lang)}
              >
                {lang}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="li-filter-group">
        <span className="li-filter-label">Level</span>
        <div className="li-filter-pills">
          {levels.map(lvl => (
            <button
              key={lvl}
              className={`li-filter-pill ${filters.level === lvl ? 'active' : ''}`}
              onClick={() => onFilterChange('level', lvl)}
            >
              {lvl}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
