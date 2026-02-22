import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  type Node,
  type Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import dagre from '@dagrejs/dagre';
import { getCharacterRelationships } from '@/api/characters';
import { ROLE_TYPE_MAP } from '@/utils/constants';

interface Props {
  novelId: string;
}

const NODE_WIDTH = 140;
const NODE_HEIGHT = 50;

function layoutNodes(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 100 });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);

  return nodes.map((n) => {
    const pos = g.node(n.id);
    return { ...n, position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 } };
  });
}

export default function RelationshipGraph({ novelId }: Props) {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  const load = useCallback(async (nid: string) => {
    try {
      const data = await getCharacterRelationships(nid);

      const rawNodes: Node[] = data.nodes.map((n) => {
        const role = ROLE_TYPE_MAP[n.role_type || 'minor'];
        return {
          id: n.id,
          data: { label: `${n.name}\n(${role?.label || '未知'})` },
          position: { x: 0, y: 0 },
          style: {
            border: `2px solid ${role?.color || '#999'}`,
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: 13,
            fontWeight: 600,
            background: '#fff',
            whiteSpace: 'pre-line' as const,
            textAlign: 'center' as const,
          },
        };
      });

      const rawEdges: Edge[] = data.edges.map((e, i) => ({
        id: `edge-${i}`,
        source: e.source,
        target: e.target,
        label: e.label,
        type: 'smoothstep',
        style: { stroke: '#888' },
        labelStyle: { fontSize: 11, fill: '#666' },
      }));

      setNodes(layoutNodes(rawNodes, rawEdges));
      setEdges(rawEdges);
    } catch {
      // no data yet
    }
  }, []);

  // eslint-disable-next-line react-hooks/set-state-in-effect -- data fetching on mount
  useEffect(() => { void load(novelId); }, [novelId, load]);

  const defaultViewport = useMemo(() => ({ x: 50, y: 50, zoom: 0.9 }), []);

  if (nodes.length === 0) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#999' }}>
        暂无关系数据
      </div>
    );
  }

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      defaultViewport={defaultViewport}
      fitView
      attributionPosition="bottom-left"
    >
      <Controls />
      <MiniMap />
      <Background />
    </ReactFlow>
  );
}
