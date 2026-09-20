import { useState } from 'react'
import { NavLink } from 'react-router-dom'

export default function Navbar() {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <nav className="navbar">
      <NavLink to="/" className="navbar-brand" onClick={() => setIsOpen(false)}>
        Smart Placement
      </NavLink>
      <button className="hamburger" onClick={() => setIsOpen(!isOpen)} aria-label="Toggle menu">
        {isOpen ? '✕' : '☰'}
      </button>
      <div className={`nav-links ${isOpen ? 'open' : ''}`}>
        <NavLink to="/" className="nav-link" onClick={() => setIsOpen(false)} end>Home</NavLink>
        <NavLink to="/interview" className="nav-link" onClick={() => setIsOpen(false)}>Mock Interview</NavLink>
        <NavLink to="/resume" className="nav-link" onClick={() => setIsOpen(false)}>Resume Suite</NavLink>
        <NavLink to="/learning" className="nav-link" onClick={() => setIsOpen(false)}>Learning</NavLink>
        <NavLink to="/doc-qa" className="nav-link" onClick={() => setIsOpen(false)}>Doc Q&A</NavLink>
        <NavLink to="/roadmap" className="nav-link" onClick={() => setIsOpen(false)}>Roadmap</NavLink>
      </div>
    </nav>
  )
}
