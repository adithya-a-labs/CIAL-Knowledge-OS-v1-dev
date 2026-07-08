import { useState } from 'react';
import { Search, X, Info } from 'lucide-react';
import { KG_NODES, KG_EDGES, KG_NODE_TYPE_META } from '@/data/knowledgeGraphData';
import type { KGNode } from '@/data/knowledgeGraphData';

const NODE_RADIUS: Record<string, number> = {
  hub: 28,
  department: 20,
  doc_type: 16,
  expert: 16,
  policy: 16,
  topic: 16,
};

export default function KnowledgeGraphPage() {
  const [selectedNode, setSelectedNode] = useState<KGNode | null>(null);
  const [search, setSearch] = useState('');
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  const searchLower = search.toLowerCase();
  const highlighted = search
    ? new Set(KG_NODES.filter(n => n.label.toLowerCase().includes(searchLower)).map(n => n.id))
    : null;

  const getNodeOpacity = (nodeId: string) => {
    if (!highlighted) return 1;
    return highlighted.has(nodeId) ? 1 : 0.25;
  };

  const getEdgeOpacity = (sourceId: string, targetId: string) => {
    if (!highlighted) return 0.35;
    return highlighted.has(sourceId) || highlighted.has(targetId) ? 0.7 : 0.1;
  };

  return (
    <div className="fluid-section" data-testid="knowledge-graph-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5">
        <div>
          <h1 className="text-xl font-bold text-[#1a2e14]">Knowledge Graph</h1>
          <p className="text-sm text-[#5a7a52] mt-0.5">Visualize relationships between knowledge entities across CIAL.</p>
        </div>
      </div>

      <div className="flex flex-col gap-4 xl:flex-row">
        {/* Graph Panel */}
        <div className="responsive-card min-w-0 flex-1 overflow-hidden border border-[#e2eedd] bg-white shadow-sm">
          {/* Toolbar */}
          <div className="flex flex-col gap-3 border-b border-[#f0f7ed] px-4 py-3 sm:flex-row sm:items-center">
            <div className="relative min-w-0 flex-1 sm:max-w-xs">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#7a9a72]" />
              <input
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search nodes..."
                className="w-full pl-8 pr-3 py-1.5 text-sm bg-[#f8fdf6] border border-[#ddecd6] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#4a7c3f]/30"
                data-testid="graph-search"
              />
              {search && (
                <button onClick={() => setSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-[#7a9a72] hover:text-[#1a2e14]">
                  <X size={12} />
                </button>
              )}
            </div>
            <span className="text-xs text-[#5a7a52]">{KG_NODES.length} nodes · {KG_EDGES.length} connections</span>
          </div>

          {/* SVG Graph */}
          <div className="scrollbar-soft overflow-auto p-2">
            <svg
              viewBox="0 0 800 560"
              className="mx-auto aspect-[10/7] w-full max-w-[800px]"
              style={{ minHeight: 400 }}
            >
              {/* Edges */}
              {KG_EDGES.map(edge => {
                const src = KG_NODES.find(n => n.id === edge.source);
                const tgt = KG_NODES.find(n => n.id === edge.target);
                if (!src || !tgt) return null;
                const opacity = getEdgeOpacity(edge.source, edge.target);
                const isHighlighted = opacity > 0.5;
                return (
                  <line
                    key={edge.id}
                    x1={src.x}
                    y1={src.y}
                    x2={tgt.x}
                    y2={tgt.y}
                    stroke={isHighlighted ? '#4a7c3f' : '#c5dfc0'}
                    strokeWidth={isHighlighted ? 1.5 : 1}
                    opacity={opacity}
                  />
                );
              })}

              {/* Nodes */}
              {KG_NODES.map(node => {
                const r = NODE_RADIUS[node.type] ?? 16;
                const opacity = getNodeOpacity(node.id);
                const isSelected = selectedNode?.id === node.id;
                const isHovered = hoveredNode === node.id;
                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x},${node.y})`}
                    onClick={() => setSelectedNode(isSelected ? null : node)}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                    className="cursor-pointer"
                    opacity={opacity}
                    data-testid={`graph-node-${node.id}`}
                  >
                    <circle
                      r={isSelected || isHovered ? r + 4 : r}
                      fill={node.color}
                      stroke={isSelected ? '#fff' : 'transparent'}
                      strokeWidth={isSelected ? 3 : 0}
                      className="transition-all duration-150"
                      filter={isSelected ? 'drop-shadow(0 0 8px rgba(74,124,63,0.6))' : undefined}
                    />
                    <text
                      textAnchor="middle"
                      dy={r + 14}
                      fontSize={node.type === 'hub' ? 11 : 9}
                      fontWeight={node.type === 'hub' ? 700 : 500}
                      fill="#1a2e14"
                      className="select-none pointer-events-none"
                    >
                      {node.label}
                    </text>
                    {node.count !== undefined && (
                      <text
                        textAnchor="middle"
                        dy={4}
                        fontSize={node.type === 'hub' ? 10 : 8}
                        fontWeight={600}
                        fill="white"
                        className="select-none pointer-events-none"
                      >
                        {node.count}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-3 px-4 py-3 border-t border-[#f0f7ed]">
            {Object.entries(KG_NODE_TYPE_META).map(([type, meta]) => (
              <div key={type} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: meta.color }} />
                <span className="text-[10px] text-[#5a7a52]">{meta.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Detail Panel */}
        <div className="grid gap-4 xl:w-72 xl:flex-shrink-0">
          {selectedNode ? (
            <div className="responsive-card border border-[#e2eedd] bg-white p-5 shadow-sm" data-testid="graph-detail-panel">
              <div className="flex items-start justify-between mb-3">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ backgroundColor: selectedNode.color + '20' }}>
                  <div className="w-4 h-4 rounded-full" style={{ backgroundColor: selectedNode.color }} />
                </div>
                <button onClick={() => setSelectedNode(null)} className="p-1 rounded hover:bg-[#f0f7ed] text-[#5a7a52]"><X size={14} /></button>
              </div>
              <h3 className="text-base font-bold text-[#1a2e14]">{selectedNode.label}</h3>
              <span className="inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full font-medium" style={{ backgroundColor: selectedNode.color + '18', color: selectedNode.color }}>
                {KG_NODE_TYPE_META[selectedNode.type]?.label}
              </span>
              <p className="text-xs text-[#5a7a52] mt-3 leading-relaxed">{selectedNode.description}</p>
              {selectedNode.count !== undefined && (
                <div className="mt-3 p-3 rounded-lg bg-[#f8fdf6] border border-[#e2eedd]">
                  <p className="text-2xl font-bold text-[#4a7c3f]">{selectedNode.count.toLocaleString()}</p>
                  <p className="text-xs text-[#5a7a52]">Connected items</p>
                </div>
              )}
              <div className="mt-3 pt-3 border-t border-[#f0f7ed]">
                <p className="text-xs font-semibold text-[#1a2e14] mb-2">Connected to</p>
                <div className="space-y-1">
                  {KG_EDGES.filter(e => e.source === selectedNode.id || e.target === selectedNode.id).slice(0, 5).map(edge => {
                    const otherId = edge.source === selectedNode.id ? edge.target : edge.source;
                    const other = KG_NODES.find(n => n.id === otherId);
                    if (!other) return null;
                    return (
                      <button key={edge.id} onClick={() => setSelectedNode(other)} className="flex items-center gap-2 w-full text-left hover:bg-[#f0f7ed] rounded-lg px-2 py-1.5 transition-colors">
                        <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: other.color }} />
                        <span className="text-xs text-[#1a2e14]">{other.label}</span>
                        {edge.label && <span className="text-[10px] text-[#7a9a72] ml-auto">{edge.label}</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div className="responsive-card border border-[#e2eedd] bg-white p-5 text-center shadow-sm" data-testid="graph-hint-panel">
              <div className="w-12 h-12 rounded-full bg-[#f0f7ed] flex items-center justify-center mx-auto mb-3">
                <Info size={20} className="text-[#4a7c3f]" />
              </div>
              <p className="text-sm font-medium text-[#1a2e14]">Click any node</p>
              <p className="text-xs text-[#5a7a52] mt-1">Select a node to see its details, connections, and related knowledge entities.</p>
              <div className="mt-4 space-y-2 text-left">
                <p className="text-xs font-semibold text-[#5a7a52] uppercase tracking-wide">Quick stats</p>
                <div className="space-y-1">
                  {KG_NODES.filter(n => n.type !== 'hub').slice(0, 5).map(n => (
                    <button key={n.id} onClick={() => setSelectedNode(n)} className="flex items-center gap-2 w-full hover:bg-[#f0f7ed] rounded-lg px-2 py-1.5 transition-colors text-left">
                      <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: n.color }} />
                      <span className="text-xs text-[#1a2e14]">{n.label}</span>
                      {n.count && <span className="text-[10px] text-[#7a9a72] ml-auto">{n.count}</span>}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
