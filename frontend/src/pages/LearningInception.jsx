import { useState, useMemo } from 'react'
import TopicCard from '../components/learning/TopicCard'
import ResourceCard from '../components/learning/ResourceCard'
import ResourceFilters from '../components/learning/ResourceFilters'
import technicalData from '../data/technicalResources.json'
import softSkillData from '../data/softSkillResources.json'

// Emoji icons for topics — fallback to 📚 for any unmapped topic
const TOPIC_ICONS = {
  // Technical
  C: '©️', 'C++': '⚙️', Java: '☕', Python: '🐍', JavaScript: '🟨', TypeScript: '🔷',
  HTML: '🌐', CSS: '🎨', 'Tailwind CSS': '💨', React: '⚛️', 'Vue.js': '💚', Angular: '🅰️',
  'Next.js': '▲', 'Node.js': '🟩', 'Express.js': '🚂', Django: '🎸', Flask: '🧪',
  FastAPI: '⚡', DBMS: '🗄️', SQL: '📊', MySQL: '🐬', PostgreSQL: '🐘', MongoDB: '🍃',
  SQLite: '📁', DSA: '🧮', OOP: '🧱', 'Operating System': '🖥️', 'Computer Networks': '🌍',
  COA: '🔌', 'Compiler Design': '🔧', TOC: '📐', 'Software Engineering': '🏗️',
  'Machine Learning': '🤖', 'Deep Learning': '🧠', NLP: '💬', 'Computer Vision': '👁️',
  'Neural Networks': '🕸️', 'AI Fundamentals': '🤖', 'Generative AI': '✨', 'Agentic AI': '🦾',
  'Reinforcement Learning': '🎮', 'Recommendation Systems': '🎯', MLOps: '📦',
  'Python for Data Science': '📈', NumPy: '🔢', Pandas: '🐼', Matplotlib: '📉',
  Seaborn: '🌊', 'Scikit-learn': '⚗️', Statistics: '📊', Probability: '🎲',
  Git: '🔀', GitHub: '🐙', Docker: '🐳', Kubernetes: '☸️', 'CI/CD': '🔄',
  Linux: '🐧', Bash: '💻',
  // Soft Skills
  Communication: '💬', 'Problem-solving': '🧩', Teamwork: '🤝', Leadership: '👑',
  Adaptability: '🔄', 'Time management': '⏰', 'Critical thinking': '🔍',
  'Conflict resolution': '🕊️', 'Decision-making': '⚖️', Accountability: '✅',
  Initiative: '🚀', 'Emotional intelligence': '❤️', Resilience: '💪',
  'Learning mindset': '📖', Professionalism: '👔',
}

function getIcon(topic) {
  return TOPIC_ICONS[topic] || '📚'
}

// Group resources by topic and count
function getTopics(data) {
  const map = {}
  data.forEach(r => {
    if (!map[r.topic]) map[r.topic] = []
    map[r.topic].push(r)
  })
  return Object.keys(map)
    .sort()
    .map(name => ({ name, count: map[name].length }))
}

export default function LearningInception() {
  // View states: 'landing' | 'topics' | 'resources'
  const [view, setView] = useState('landing')
  // 'technical' | 'soft'
  const [section, setSection] = useState(null)
  const [selectedTopic, setSelectedTopic] = useState(null)
  const [filters, setFilters] = useState({
    category: 'All',
    language: 'All',
    level: 'All Levels',
  })

  const currentData = section === 'technical' ? technicalData : softSkillData
  const topics = useMemo(() => getTopics(currentData), [currentData])
  const topicResources = useMemo(
    () => currentData.filter(r => r.topic === selectedTopic),
    [currentData, selectedTopic]
  )

  // Apply filters
  const filteredResources = useMemo(() => {
    return topicResources.filter(r => {
      if (filters.category !== 'All' && r.category !== filters.category) return false
      if (filters.language !== 'All' && r.language !== filters.language) return false
      if (filters.level !== 'All Levels' && r.level !== filters.level) return false
      return true
    })
  }, [topicResources, filters])

  function handleFilterChange(key, value) {
    setFilters(prev => ({ ...prev, [key]: value }))
  }

  function openSection(sec) {
    setSection(sec)
    setView('topics')
    setSelectedTopic(null)
    setFilters({ category: 'All', language: 'All', level: 'All Levels' })
  }

  function openTopic(topicName) {
    setSelectedTopic(topicName)
    setView('resources')
    setFilters({ category: 'All', language: 'All', level: 'All Levels' })
  }

  function goBack() {
    if (view === 'resources') {
      setView('topics')
      setSelectedTopic(null)
    } else if (view === 'topics') {
      setView('landing')
      setSection(null)
    }
  }

  const sectionLabel = section === 'technical' ? 'Technical Skills' : 'Soft Skill Development'

  return (
    <div className="li-page">
      {/* Breadcrumb */}
      <div className="li-breadcrumb">
        <button
          className={`li-bread-item ${view === 'landing' ? 'active' : ''}`}
          onClick={() => { setView('landing'); setSection(null); setSelectedTopic(null) }}
        >
          Learning Inception
        </button>
        {view !== 'landing' && (
          <>
            <span className="li-bread-sep">›</span>
            <button
              className={`li-bread-item ${view === 'topics' ? 'active' : ''}`}
              onClick={() => { setView('topics'); setSelectedTopic(null) }}
            >
              {sectionLabel}
            </button>
          </>
        )}
        {view === 'resources' && selectedTopic && (
          <>
            <span className="li-bread-sep">›</span>
            <span className="li-bread-item active">{selectedTopic}</span>
          </>
        )}
      </div>

      {/* ─── Landing ─── */}
      {view === 'landing' && (
        <>
          <div className="li-header">
            <h1 className="li-title">Learning Inception</h1>
            <p className="li-subtitle">
              Discover curated learning resources and start your learning journey today.
            </p>
          </div>

          <div className="li-sections-grid">
            <div className="li-section-card" onClick={() => openSection('technical')} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && openSection('technical')}>
              <span className="li-section-icon">T</span>
              <h2 className="li-section-title">Technical Skills</h2>
              <p className="li-section-desc">
                Learn core computer science, programming, AI, development and other technical subjects.
              </p>
              <span className="li-section-count">{technicalData.length} Resources · {getTopics(technicalData).length} Topics</span>
              <span className="li-section-action">Explore →</span>
            </div>
            <div className="li-section-card" onClick={() => openSection('soft')} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && openSection('soft')}>
              <span className="li-section-icon">S</span>
              <h2 className="li-section-title">Soft Skill Development</h2>
              <p className="li-section-desc">
                Improve communication, interview skills, personality development and other professional skills.
              </p>
              <span className="li-section-count">{softSkillData.length} Resources · {getTopics(softSkillData).length} Topics</span>
              <span className="li-section-action">Explore →</span>
            </div>
          </div>
        </>
      )}

      {/* ─── Topics ─── */}
      {view === 'topics' && (
        <>
          <div className="li-header">
            <button className="li-back-btn" onClick={goBack}>← Back</button>
            <h1 className="li-title">{sectionLabel}</h1>
            <p className="li-subtitle">
              {topics.length} topics · {currentData.length} resources
            </p>
          </div>

          <div className="li-topics-grid">
            {topics.map(t => (
              <TopicCard
                key={t.name}
                name={t.name}
                count={t.count}
                icon={getIcon(t.name)}
                onClick={() => openTopic(t.name)}
              />
            ))}
          </div>
        </>
      )}

      {/* ─── Resources ─── */}
      {view === 'resources' && (
        <>
          <div className="li-header">
            <button className="li-back-btn" onClick={goBack}>← Back to Topics</button>
            <h1 className="li-title">{getIcon(selectedTopic)} {selectedTopic}</h1>
            <p className="li-subtitle">
              {filteredResources.length} of {topicResources.length} resources
            </p>
          </div>

          <ResourceFilters
            resources={topicResources}
            filters={filters}
            onFilterChange={handleFilterChange}
          />

          {filteredResources.length > 0 ? (
            <div className="li-resources-grid">
              {filteredResources.map((r, i) => (
                <ResourceCard key={`${r.channel}-${r.url}-${i}`} resource={r} />
              ))}
            </div>
          ) : (
            <div className="li-empty">
              <span className="li-empty-icon">—</span>
              <p className="li-empty-text">No resources match the selected filters.</p>
              <button
                className="li-empty-reset"
                onClick={() => setFilters({ category: 'All', language: 'All', level: 'All Levels' })}
              >
                Reset Filters
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
