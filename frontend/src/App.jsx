import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import MockInterview from './pages/MockInterview'
import ResumeSuite from './pages/ResumeSuite'

export default function App() {
  const location = useLocation()

  // Scroll to top on route change
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  return (
    <>
      <Navbar />
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/interview" element={<MockInterview />} />
          <Route path="/resume" element={<ResumeSuite />} />
        </Routes>
      </main>
    </>
  )
}
