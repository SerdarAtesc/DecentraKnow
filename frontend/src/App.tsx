import { Routes, Route } from 'react-router-dom'
import { WalletContext, useWalletProvider } from './hooks/useWallet'
import Layout from './components/Layout'
import UploadPage from './pages/UploadPage'
import SearchPage from './pages/SearchPage'
import PaidSearchPage from './pages/PaidSearchPage'
import WalletPage from './pages/WalletPage'
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
          <Route path="paid-search" element={<PaidSearchPage />} />
          <Route path="wallet" element={<WalletPage />} />
          <Route path="graph" element={<GraphPage />} />
        </Route>
      </Routes>
    </WalletContext.Provider>
  )
}

export default App
