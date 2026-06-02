import { Brain, Database, Shield, Cpu } from 'lucide-react'

function DashboardPage() {
  const features = [
    {
      icon: Cpu,
      title: 'AI Embeddings',
      description: 'Transform content into semantic vectors using OpenAI text-embedding-3-small for intelligent retrieval.',
    },
    {
      icon: Brain,
      title: 'RAG Engine',
      description: 'Ask questions and get answers grounded in verified knowledge, with full source attribution.',
    },
    {
      icon: Database,
      title: 'IPFS Storage',
      description: 'Content stored on decentralized IPFS network. Immutable, censorship-resistant, always available.',
    },
    {
      icon: Shield,
      title: 'Stellar Blockchain',
      description: 'Every knowledge asset registered on Soroban smart contracts for provenance and integrity verification.',
    },
  ]

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold mb-2">
          Decentralized AI Knowledge Network
        </h1>
        <p className="text-dark-200 text-lg">
          Upload knowledge, search semantically, and query with AI — all verified on the Stellar blockchain.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {features.map((feature) => (
          <div key={feature.title} className="card hover:border-stellar-600/50 transition-colors">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 bg-stellar-600/20 rounded-lg flex items-center justify-center shrink-0">
                <feature.icon className="w-6 h-6 text-stellar-400" />
              </div>
              <div>
                <h3 className="font-semibold text-lg mb-1">{feature.title}</h3>
                <p className="text-dark-200 text-sm">{feature.description}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2 className="text-xl font-semibold mb-4">Pipeline</h2>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          {['Content', 'Embedding', 'Vector DB', 'IPFS', 'Blockchain', 'AI Retrieval'].map(
            (step, i) => (
              <div key={step} className="flex items-center gap-3">
                <span className="bg-stellar-600/20 text-stellar-300 px-3 py-1.5 rounded-lg font-medium">
                  {step}
                </span>
                {i < 5 && <span className="text-dark-300">→</span>}
              </div>
            )
          )}
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
