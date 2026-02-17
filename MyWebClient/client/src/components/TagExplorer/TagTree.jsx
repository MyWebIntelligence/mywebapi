import { useState, useMemo, useCallback } from 'react'
import { Badge } from 'react-bootstrap'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors
} from '@dnd-kit/core'
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  arrayMove
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

/* ------------------------------------------------------------------ */
/*  Helpers: flat array -> tree                                        */
/* ------------------------------------------------------------------ */

function buildTree(flat) {
  const map = {}
  const roots = []

  flat.forEach((t) => {
    map[t.id] = { ...t, children: [] }
  })

  flat.forEach((t) => {
    const node = map[t.id]
    if (t.parent_id && map[t.parent_id]) {
      map[t.parent_id].children.push(node)
    } else {
      roots.push(node)
    }
  })

  return roots
}

function flattenTree(nodes, parentId = null, depth = 0) {
  const result = []
  nodes.forEach((node, index) => {
    result.push({ ...node, parent_id: parentId, depth, position: index })
    if (node.children && node.children.length > 0) {
      result.push(...flattenTree(node.children, node.id, depth + 1))
    }
  })
  return result
}

function flattenWithDepth(tree, depth = 0) {
  const result = []
  tree.forEach((node) => {
    result.push({ ...node, depth })
    if (node.children && node.children.length > 0) {
      result.push(...flattenWithDepth(node.children, depth + 1))
    }
  })
  return result
}

/* ------------------------------------------------------------------ */
/*  SortableTagNode                                                    */
/* ------------------------------------------------------------------ */

function SortableTagNode({ tag, depth, onEdit, onDelete, onAddChild }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging
  } = useSortable({ id: String(tag.id) })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    marginLeft: depth * 20,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '6px 8px',
    borderBottom: '1px solid #edf1f8',
    cursor: 'grab',
    background: isDragging ? '#f0f4ff' : 'transparent'
  }

  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        <span
          style={{
            display: 'inline-block',
            width: 14,
            height: 14,
            borderRadius: 3,
            backgroundColor: tag.color || '#007bff',
            flexShrink: 0
          }}
        />
        <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {tag.name}
        </span>
        {tag.count !== undefined && tag.count !== null && (
          <Badge bg="secondary" pill style={{ fontSize: '0.7rem' }}>
            {tag.count}
          </Badge>
        )}
      </div>

      <div style={{ display: 'flex', gap: 2, flexShrink: 0 }}>
        <button
          className="tag-node-control"
          title="Ajouter un sous-tag"
          onClick={(e) => { e.stopPropagation(); onAddChild(tag.id) }}
        >
          <i className="fas fa-plus" />
        </button>
        <button
          className="tag-node-control"
          title="Modifier"
          onClick={(e) => { e.stopPropagation(); onEdit(tag) }}
        >
          <i className="fas fa-pencil-alt" />
        </button>
        <button
          className="tag-node-control"
          title="Supprimer"
          onClick={(e) => { e.stopPropagation(); onDelete(tag.id) }}
        >
          <i className="fas fa-trash" />
        </button>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/*  TagTree                                                            */
/* ------------------------------------------------------------------ */

export default function TagTree({ tags = [], onReorder, onEdit, onDelete, onAddChild }) {
  const tree = useMemo(() => buildTree(tags), [tags])
  const flatNodes = useMemo(() => flattenWithDepth(tree), [tree])
  const sortableIds = useMemo(() => flatNodes.map((n) => String(n.id)), [flatNodes])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor)
  )

  const handleDragEnd = useCallback(
    (event) => {
      const { active, over } = event
      if (!over || active.id === over.id) return

      const oldIndex = flatNodes.findIndex((n) => String(n.id) === active.id)
      const newIndex = flatNodes.findIndex((n) => String(n.id) === over.id)

      if (oldIndex === -1 || newIndex === -1) return

      const reordered = arrayMove(flatNodes, oldIndex, newIndex)

      // Determine new parent_id: adopt the parent of the node we dropped onto
      const droppedOnNode = flatNodes[newIndex]
      const movedNode = flatNodes[oldIndex]

      const updatedFlat = reordered.map((node, idx) => {
        if (String(node.id) === active.id) {
          return {
            ...node,
            parent_id: droppedOnNode.parent_id,
            position: idx
          }
        }
        return { ...node, position: idx }
      })

      // Strip tree helper fields and return clean flat array
      const cleaned = updatedFlat.map(({ children, depth, ...rest }) => rest)
      if (onReorder) onReorder(cleaned)
    },
    [flatNodes, onReorder]
  )

  if (flatNodes.length === 0) {
    return (
      <div className="tag-tree" style={{ color: '#888', padding: 16, textAlign: 'center' }}>
        Aucun tag
      </div>
    )
  }

  return (
    <div className="tag-tree">
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={sortableIds} strategy={verticalListSortingStrategy}>
          {flatNodes.map((node) => (
            <SortableTagNode
              key={node.id}
              tag={node}
              depth={node.depth}
              onEdit={onEdit}
              onDelete={onDelete}
              onAddChild={onAddChild}
            />
          ))}
        </SortableContext>
      </DndContext>
    </div>
  )
}
