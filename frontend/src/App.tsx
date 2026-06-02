import { Routes, Route } from 'react-router-dom'
import { WalletContext, useWalletProvider } from './hooks/useWallet'
import Layout from './components/Layout'
import UploadPage from './pages/UploadPage'
import SearchPage from './pages/SearchPage'
import RAGChatPage from './pages/RAGChatPage'
import DashboardPage from './pages/DashboardPage'
import GraphPage from './pages/GraphPage'

function App() {
  const wallet = useWalletProvider()

  return (
    <WalletContext.Provider value={wallet}>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="search" element={<SearchPage />} />
          <Route path="chat" element={<RAGChatPage />} />
          <Route path="graph" element={<GraphPage />} />
        </Route>
      </Routes>
    </WalletContext.Provider>
  )
}

export default App
