import { useState, useEffect, useCallback, useRef } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { Network, RefreshCw, Filter, Database } from 'lucide-react'
import { api } from '../services/api'

interface GraphNode {
  id: string
  label: string
  type: string
  source_hash: string
}

interface GraphEdge {
  source: string
  target: string
  relation: string
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  total_nodes: number
  total_edges: number
}

const TYPE_COLORS: Record<string, string> = {
  technology: '#3b82f6',
  organization: '#8b5cf6',
  concept: '#10b981',
  person: '#f59e0b',
  protocol: '#ef4444',
  token: '#ec4899',
}

function GraphPage() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const [rebuilding, setRebuilding] = useState(false)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [filterType, setFilterType] = useState<string>('')
  const graphRef = useRef<any>(null)

  const fetchGraph = useCallback(async () => {
    setLoading(true)
    try {
      const data = await api.graph() as GraphData
      setGraphData(data)
    } catch (err) {
      console.error('Failed to fetch graph:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchGraph()
  }, [fetchGraph])

  const forceGraphData = graphData
    ? {
        nodes: graphData.nodes
          .filter(n => !filterType || n.type === filterType)
          .map(n => ({ ...n, val: 3 })),
        links: graphData.edges
          .filter(e => {
            if (!filterType) return true
            const nodeIds = new Set(
              graphData.nodes.filter(n => n.type === filterType).map(n => n.id)
            )
            return nodeIds.has(e.source as string) || nodeIds.has(e.target as string)
          })
          .map(e => ({ ...e, source: e.source, target: e.target })),
      }
    : { nodes: [], links: [] }

  const entityTypes = graphData
    ? [...new Set(graphData.nodes.map(n => n.type))]
    : []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Network className="w-8 h-8 text-purple-400" />
          <div>
            <h1 className="text-2xl font-bold text-white">Knowledge Graph</h1>
            <p className="text-gray-400 text-sm">
              Interactive visualization of entities and their relationships
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {entityTypes.length > 0 && (
            <select
              value={filterType}
              onChange={e => setFilterType(e.target.value)}
              className="input-field text-sm w-40"
            >
              <option value="">All types</option>
              {entityTypes.map(t => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={async () => {
              setRebuilding(true)
              try {
                await api.rebuildGraph()
                await fetchGraph()
              } catch (err) {
                console.error('Rebuild failed:', err)
              } finally {
                setRebuilding(false)
              }
            }}
            disabled={rebuilding}
            className="btn-secondary flex items-center gap-2 disabled:opacity-50"
          >
            <Database className="w-4 h-4" />
            {rebuilding ? 'Rebuilding...' : 'Rebuild from DB'}
          </button>
          <button onClick={fetchGraph} className="btn-primary flex items-center gap-2">
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-96">
          <div className="text-gray-400 flex items-center gap-2">
            <RefreshCw className="w-5 h-5 animate-spin" />
            Loading graph...
          </div>
        </div>
      ) : !graphData || graphData.nodes.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-96 text-gray-400">
          <Network className="w-16 h-16 mb-4 opacity-30" />
          <p className="text-lg">No graph data yet</p>
          <p className="text-sm mt-2">
            Upload content to automatically extract entities and relationships
          </p>
        </div>
      ) : (
        <div className="bg-gray-800/50 rounded-xl border border-gray-700 overflow-hidden relative">
          <div className="absolute top-4 left-4 z-10 bg-gray-900/90 rounded-lg p-3 text-xs space-y-1">
            <div className="text-gray-300 font-medium mb-2 flex items-center gap-1">
              <Filter className="w-3 h-3" />
              Legend
            </div>
            {Object.entries(TYPE_COLORS).map(([type, color]) => (
              <div key={type} className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <span className="text-gray-400 capitalize">{type}</span>
              </div>
            ))}
          </div>

          {selectedNode && (
            <div className="absolute top-4 right-4 z-10 bg-gray-900/90 rounded-lg p-4 max-w-xs">
              <h3 className="text-white font-medium">{selectedNode.label}</h3>
              <p className="text-gray-400 text-sm capitalize mt-1">
                Type: {selectedNode.type}
              </p>
              <button
                onClick={() => setSelectedNode(null)}
                className="text-gray-500 text-xs mt-2 hover:text-gray-300"
              >
                Close
              </button>
            </div>
          )}

          <ForceGraph2D
            ref={graphRef}
            graphData={forceGraphData}
            nodeLabel="label"
            nodeColor={(node: any) => TYPE_COLORS[node.type] || '#6b7280'}
            nodeRelSize={6}
            linkLabel="relation"
            linkColor={() => '#4b5563'}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            onNodeClick={(node: any) => setSelectedNode(node)}
            backgroundColor="#111827"
            width={typeof window !== 'undefined' ? window.innerWidth - 320 : 800}
            height={500}
          />

          <div className="p-4 border-t border-gray-700 flex justify-between text-sm text-gray-400">
            <span>
              {graphData.total_nodes} entities, {graphData.total_edges} relationships
            </span>
            <span>Click on a node for details. Scroll to zoom. Drag to pan.</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default GraphPage
