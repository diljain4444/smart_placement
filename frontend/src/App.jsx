import { useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import MockInterview from './pages/MockInterview'
import ResumeSuite from './pages/ResumeSuite'
import LearningInception from './pages/LearningInception'
import DocQA from './pages/DocQA'
import Roadmap from './pages/Roadmap'

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
          <Route path="/learning" element={<LearningInception />} />
          <Route path="/doc-qa" element={<DocQA />} />
          <Route path="/roadmap" element={<Roadmap />} />
        </Routes>
      </main>
    </>
  )
}
