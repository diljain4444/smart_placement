export default function TopicCard({ name, count, icon, onClick }) {
  return (
    <div className="li-topic-card" onClick={onClick} role="button" tabIndex={0} onKeyDown={e => e.key === 'Enter' && onClick()}>
      <span className="li-topic-icon">{icon}</span>
      <h3 className="li-topic-name">{name}</h3>
      <p className="li-topic-count">
        {count} {count === 1 ? 'Resource' : 'Resources'}
      </p>
      <span className="li-topic-action">View →</span>
    </div>
  )
}
