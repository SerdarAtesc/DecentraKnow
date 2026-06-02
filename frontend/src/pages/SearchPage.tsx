import { useState } from 'react'
import { Search, ExternalLink, Loader2 } from 'lucide-react'
import { api } from '../services/api'

interface SearchResultItem {
  content_hash: string
  title: string
  content_preview: string
  score: number
  category: string
  language: string
  owner: string
  ipfs_cid: string
  timestamp: string
}

interface SearchResponseData {
  results: SearchResultItem[]
  query: string
  total: number
}

function SearchPage() {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<SearchResponseData | null>(null)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    try {
      const res = await api.search({
        query,
        top_k: 10,
        category: category || undefined,
      }) as SearchResponseData
      setResults(res)
    } catch (err) {
      console.error('Search failed:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-1">Semantic Search</h1>
        <p className="text-dark-200">Search the knowledge network by meaning, not just keywords.</p>
      </div>

      <form onSubmit={handleSearch} className="flex gap-3">
        <div className="flex-1 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-dark-200" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask anything... (e.g., 'How does proof of stake work?')"
            className="input-field pl-12"
          />
        </div>
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="input-field w-40"
        >
          <option value="">All Categories</option>
          <option value="science">Science</option>
          <option value="technology">Technology</option>
          <option value="finance">Finance</option>
          <option value="blockchain">Blockchain</option>
          <option value="ai">AI / ML</option>
        </select>
        <button type="submit" disabled={loading} className="btn-primary">
          {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Search'}
        </button>
      </form>

      {results && (
        <div className="space-y-4">
          <p className="text-sm text-dark-200">
            Found {results.total} results for "{results.query}"
          </p>

          {results.results.map((item) => (
            <div key={item.content_hash} className="card hover:border-stellar-600/30 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-semibold truncate">{item.title}</h3>
                    <span className="text-xs bg-stellar-600/20 text-stellar-300 px-2 py-0.5 rounded shrink-0">
                      {(item.score * 100).toFixed(1)}% match
                    </span>
                  </div>
                  <p className="text-dark-200 text-sm line-clamp-3">{item.content_preview}</p>
                  <div className="flex items-center gap-4 mt-3 text-xs text-dark-300">
                    <span className="bg-dark-600 px-2 py-0.5 rounded">{item.category}</span>
                    <span>{item.language.toUpperCase()}</span>
                    <span className="truncate max-w-[120px]">{item.owner}</span>
                  </div>
                </div>
                {item.ipfs_cid && (
                  <a
                    href={`https://ipfs.io/ipfs/${item.ipfs_cid}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-stellar-400 hover:text-stellar-300 shrink-0"
                    title="View on IPFS"
                  >
                    <ExternalLink className="w-4 h-4" />
                  </a>
                )}
              </div>
            </div>
          ))}

          {results.results.length === 0 && (
            <div className="card text-center py-12">
              <p className="text-dark-200">No results found. Try a different query.</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default SearchPage
