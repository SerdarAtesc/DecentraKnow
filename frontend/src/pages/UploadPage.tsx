import { useState } from 'react'
import { Upload, Link, FileText, CheckCircle, AlertCircle, Loader2 } from 'lucide-react'
import { api } from '../services/api'
import { useWallet } from '../hooks/useWallet'
import { soroban } from '../services/soroban'

type InputMode = 'text' | 'url'

interface UploadResult {
  success: boolean
  message: string
  content_hash?: string
  ipfs_cid?: string
  record_id?: number
  duplicate?: boolean
}

interface PrepareData {
  duplicate: boolean
  message: string
  content_hash: string
  embedding_hash: string
  sim_hash: string
  ipfs_cid: string
  title: string
  source_url: string
}

function UploadPage() {
  const { connected, publicKey, canSign, signXdr } = useWallet()
  const [mode, setMode] = useState<InputMode>('text')
  const [content, setContent] = useState('')
  const [url, setUrl] = useState('')
  const [title, setTitle] = useState('')
  const [category, setCategory] = useState('general')
  const [language, setLanguage] = useState('en')
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState<string>('')
  const [result, setResult] = useState<UploadResult | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!connected || !publicKey) return
    if (!canSign) {
      setResult({ success: false, message: 'Connect a Freighter wallet to sign the registration (demo mode is read-only).' })
      return
    }

    setLoading(true)
    setResult(null)

    try {
      const payload = {
        ...(mode === 'text' ? { content } : { url }),
        owner: publicKey,
        category,
        language,
        title: title || undefined,
      }

      // 1) Backend computes embedding / SimHash / IPFS (no chain write).
      setStep('Embedding & pinning to IPFS…')
      const prep = (await api.uploadPrepare(payload)) as PrepareData
      if (prep.duplicate) {
        setResult({ success: false, message: prep.message, content_hash: prep.content_hash, duplicate: true })
        return
      }

      // 2) The connected wallet signs register_knowledge -> the owner is the user.
      setStep('Sign the registration in your wallet…')
      const recordId = await soroban.register(publicKey, signXdr, {
        contentHash: prep.content_hash,
        embeddingHash: prep.embedding_hash,
        simHash: prep.sim_hash,
        ipfsCid: prep.ipfs_cid,
        sourceUrl: prep.source_url,
      })

      // 3) Backend indexes the vector under the assigned on-chain id.
      setStep('Indexing…')
      await api.uploadFinalize({ content_hash: prep.content_hash, record_id: recordId })

      setResult({
        success: true,
        message: `Registered on-chain by you (record #${recordId}). You now earn when it answers searches.`,
        content_hash: prep.content_hash,
        ipfs_cid: prep.ipfs_cid,
        record_id: recordId,
      })
    } catch (err) {
      setResult({ success: false, message: err instanceof Error ? err.message : 'Upload failed' })
    } finally {
      setLoading(false)
      setStep('')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold mb-1">Upload Knowledge</h1>
        <p className="text-dark-200">Add content to the decentralized knowledge network.</p>
      </div>

      {!connected && (
        <div className="card border-yellow-500/30 bg-yellow-500/5">
          <p className="text-yellow-400 flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            Connect your Stellar wallet to upload content.
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setMode('text')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              mode === 'text' ? 'bg-stellar-600 text-white' : 'bg-dark-600 text-dark-100'
            }`}
          >
            <FileText className="w-4 h-4" />
            Text
          </button>
          <button
            type="button"
            onClick={() => setMode('url')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
              mode === 'url' ? 'bg-stellar-600 text-white' : 'bg-dark-600 text-dark-100'
            }`}
          >
            <Link className="w-4 h-4" />
            URL
          </button>
        </div>

        {mode === 'text' ? (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="Paste or type your knowledge content here..."
            className="input-field min-h-[200px] resize-y"
            required
          />
        ) : (
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            className="input-field"
            required
          />
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Title (optional)"
            className="input-field"
          />
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="input-field"
          >
            <option value="general">General</option>
            <option value="science">Science</option>
            <option value="technology">Technology</option>
            <option value="finance">Finance</option>
            <option value="blockchain">Blockchain</option>
            <option value="ai">AI / ML</option>
          </select>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="input-field"
          >
            <option value="en">English</option>
            <option value="tr">Turkish</option>
            <option value="es">Spanish</option>
            <option value="pt">Portuguese</option>
            <option value="de">German</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={loading || !connected}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
          {loading ? (step || 'Processing…') : 'Upload & Register (wallet-signed)'}
        </button>
      </form>

      {result && (
        <div className={`card ${result.success ? 'border-green-500/30' : 'border-red-500/30'}`}>
          <div className="flex items-start gap-3">
            {result.success ? (
              <CheckCircle className="w-6 h-6 text-green-400 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-6 h-6 text-red-400 shrink-0 mt-0.5" />
            )}
            <div className="space-y-2">
              <p className={result.success ? 'text-green-400' : 'text-red-400'}>
                {result.message}
              </p>
              {result.content_hash && (
                <p className="text-sm text-dark-200">
                  <span className="font-medium">Content Hash:</span>{' '}
                  <code className="text-xs bg-dark-600 px-2 py-0.5 rounded">{result.content_hash}</code>
                </p>
              )}
              {result.ipfs_cid && (
                <p className="text-sm text-dark-200">
                  <span className="font-medium">IPFS CID:</span>{' '}
                  <code className="text-xs bg-dark-600 px-2 py-0.5 rounded">{result.ipfs_cid}</code>
                </p>
              )}
              {result.record_id !== undefined && (
                <p className="text-sm text-dark-200">
                  <span className="font-medium">On-chain record:</span>{' '}
                  <code className="text-xs bg-dark-600 px-2 py-0.5 rounded">#{result.record_id}</code>
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default UploadPage
