import React, { useCallback, useMemo, useRef, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { GraphEdge, GraphNode } from '../types';

export interface RelationshipGraphProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNodeId: string | null;
  onNodeClick: (nodeId: string) => void;
  onDocClick: (docId: string) => void;
  width?: number;
  height?: number;
}

/** Force-directed graph of entities (nodes) and triples (links). */
export function RelationshipGraph({
  nodes,
  edges,
  selectedNodeId,
  onNodeClick,
  onDocClick,
  width: widthProp,
  height: heightProp,
}: RelationshipGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0]?.contentRect ?? { width: 800, height: 600 };
      setSize({ width: Math.max(100, width), height: Math.max(100, height) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const width = widthProp ?? size.width;
  const height = heightProp ?? size.height;

  const graphData = useMemo(() => {
    const nodeList = nodes.map((n) => ({ ...n }));
    const nodeMap = new Map(nodeList.map((n) => [n.id, n]));
    const links = edges
      .filter((e) => e.source && e.target && nodeMap.has(e.source) && nodeMap.has(e.target))
      .map((e) => ({
        source: nodeMap.get(e.source)!,
        target: nodeMap.get(e.target)!,
        action: e.action,
        doc_id: e.doc_id,
        timestamp: e.timestamp,
        location: e.location,
      }));
    return {
      nodes: nodeList,
      links,
    };
  }, [nodes, edges]);

  const [hoverNode, setHoverNode] = useState<any>(null);

  const handleNodeClick = useCallback(
    (node: { id?: string }) => {
      const id = typeof node?.id === 'string' ? node.id : (node as { id: string })?.id;
      if (id) onNodeClick(id);
    },
    [onNodeClick]
  );

  if (graphData.nodes.length === 0) {
    return (
      <div className="w-full h-full flex items-center justify-center text-zinc-500 font-mono text-sm bg-zinc-950/50 rounded-lg border border-zinc-800/50">
        No nodes to display. Try searching for an entity or loading a sample.
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full">
    <ForceGraph2D
      graphData={graphData}
      width={width}
      height={height}
      nodeId="id"
      nodeLabel={(n) => (n as GraphNode).label ?? (n as { id: string }).id}
      nodeCanvasObject={(node: any, ctx, globalScale) => {
        const label = (node as GraphNode).label ?? (node as { id: string }).id;
        const isSelected = node.id === selectedNodeId;
        const isHovered = node === hoverNode;
        const count = (node as GraphNode).count ?? 1;
        const baseSize = 3 + Math.log2(1 + count);
        const size = Math.min(baseSize, 12);
        
        // Draw node circle
        ctx.beginPath();
        ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
        ctx.fillStyle = isSelected ? '#f97316' : (isHovered ? '#a1a1aa' : '#71717a');
        ctx.fill();
        
        // Draw border for selected or hovered node
        if (isSelected || isHovered) {
          ctx.strokeStyle = isSelected ? '#fb923c' : '#d4d4d8';
          ctx.lineWidth = (isSelected ? 2 : 1) / globalScale;
          ctx.stroke();
        }

        // Draw label
        const fontSize = 12 / globalScale;
        ctx.font = `${fontSize}px Inter, system-ui, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        // Only show label if zoomed in or selected or hovered
        // Obsidian shows more labels as you zoom in, and truncates long ones
        const isImportant = count > 5; // Show labels for highly connected nodes earlier
        if (globalScale > 1.2 || isSelected || isHovered || (globalScale > 0.8 && isImportant)) {
          let displayLabel = label;
          const maxCharLen = Math.floor(20 / Math.max(1, globalScale * 0.5)); // Dynamic truncation
          
          if (!isSelected && !isHovered && displayLabel.length > maxCharLen && globalScale < 2) {
            displayLabel = displayLabel.substring(0, maxCharLen) + '...';
          }

          const textWidth = ctx.measureText(displayLabel).width;
          const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.4);

          // Subtle background for the text
          ctx.fillStyle = 'rgba(9, 9, 11, 0.85)';
          const labelY = node.y + size + fontSize;
          
          // Rounded rect for label background
          const rx = node.x - bckgDimensions[0] / 2;
          const ry = labelY - bckgDimensions[1] / 2;
          const rw = bckgDimensions[0];
          const rh = bckgDimensions[1];
          const radius = 2 / globalScale;
          
          ctx.beginPath();
          ctx.moveTo(rx + radius, ry);
          ctx.lineTo(rx + rw - radius, ry);
          ctx.quadraticCurveTo(rx + rw, ry, rx + rw, ry + radius);
          ctx.lineTo(rx + rw, ry + rh - radius);
          ctx.quadraticCurveTo(rx + rw, ry + rh, rx + rw - radius, ry + rh);
          ctx.lineTo(rx + radius, ry + rh);
          ctx.quadraticCurveTo(rx, ry + rh, rx, ry + rh - radius);
          ctx.lineTo(rx, ry + radius);
          ctx.quadraticCurveTo(rx, ry, rx + radius, ry);
          ctx.closePath();
          ctx.fill();

          ctx.fillStyle = isSelected ? '#fafafa' : (isHovered ? '#e4e4e7' : '#a1a1aa');
          ctx.fillText(displayLabel, node.x, labelY);
        }
      }}
      nodePointerAreaPaint={(node: any, color, ctx) => {
        const count = (node as GraphNode).count ?? 1;
        const baseSize = 3 + Math.log2(1 + count);
        const size = Math.min(baseSize, 12);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
        ctx.fill();
      }}
      linkColor={() => '#3f3f46'}
      linkWidth={1}
      onNodeClick={handleNodeClick}
      onNodeHover={setHoverNode}
      backgroundColor="rgba(9, 9, 11, 0.5)"
      d3AlphaDecay={0.02}
      d3VelocityDecay={0.3}
    />
    </div>
  );
}
