export default function Loading({ message = 'Loading…', fullScreen = false }) {
  return (
    <div className={`loading-overlay ${fullScreen ? 'fullscreen' : ''}`}>
      <div className="loading-spinner" />
      {message && <p className="loading-message">{message}</p>}
    </div>
  )
}
