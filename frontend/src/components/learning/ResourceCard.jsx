export default function ResourceCard({ resource }) {
  const levelClass = {
    Easy: 'li-level-easy',
    Medium: 'li-level-medium',
    Hard: 'li-level-hard',
  }[resource.level] || ''

  return (
    <div className="li-resource-card">
      <h4 className="li-resource-channel">{resource.channel}</h4>

      <div className="li-resource-meta">
        {resource.category && (
          <span className="li-resource-tag li-tag-category">{resource.category}</span>
        )}
        {resource.language && (
          <span className="li-resource-tag li-tag-language">{resource.language}</span>
        )}
        {resource.level && (
          <span className={`li-resource-tag li-tag-level ${levelClass}`}>{resource.level}</span>
        )}
      </div>

      {resource.topic && (
        <p className="li-resource-topic">{resource.topic}</p>
      )}

      <a
        href={resource.url}
        target="_blank"
        rel="noopener noreferrer"
        className="li-yt-btn"
      >
        ▶ Watch on YouTube
      </a>
    </div>
  )
}
