import React, {useContext, useEffect, useState} from 'react'
import {Context} from "../../app/Context"
import TagTree from "./TagTree"
import './TagExplorer.css'
import {Button, Modal} from "react-bootstrap"

/**
 * Converts hierarchical tag tree (with children arrays) to flat array with parent_id.
 */
function treeToFlat(nodes, parentId = null) {
    const result = []
    nodes.forEach((node, index) => {
        result.push({
            id: node.id,
            name: node.name,
            color: node.color,
            parent_id: parentId,
            position: index,
        })
        if (node.children && node.children.length > 0) {
            result.push(...treeToFlat(node.children, node.id))
        }
    })
    return result
}

/**
 * Converts flat array (with parent_id) back to hierarchical tree.
 */
function flatToTree(flat) {
    const map = {}
    const roots = []

    flat.forEach(t => {
        map[t.id] = {...t, children: []}
    })

    flat.forEach(t => {
        const node = map[t.id]
        if (t.parent_id && map[t.parent_id]) {
            map[t.parent_id].children.push(node)
        } else {
            roots.push(node)
        }
    })

    return roots
}

function TagExplorer() {
    const context = useContext(Context)
    const defaultColor = '#007bff'
    const [flatTags, setFlatTags] = useState([])
    const [currentTag, setCurrentTag] = useState(null)
    const [showModal, setShowModal] = useState(false)

    const handleClose = () => setShowModal(false)

    useEffect(() => {
        setFlatTags(treeToFlat(context.tags))
    }, [context.tags])

    const handleReorder = (reorderedFlat) => {
        const tree = flatToTree(reorderedFlat)
        context.setTags(tree)
    }

    const handleEdit = (tag) => {
        setCurrentTag({...tag})
        setShowModal(true)
    }

    const handleDelete = (tagId) => {
        if (window.confirm("Are you sure to delete this tag?")) {
            const removeTag = (nodes) => {
                return nodes
                    .filter(n => n.id !== tagId)
                    .map(n => ({...n, children: removeTag(n.children || [])}))
            }
            context.setTags(removeTag(context.tags))
        }
    }

    const handleAddChild = (parentId) => {
        const newTag = {name: 'New tag', color: defaultColor, children: []}
        const addChild = (nodes) => {
            return nodes.map(n => {
                if (n.id === parentId) {
                    return {...n, children: [...(n.children || []), newTag]}
                }
                return {...n, children: addChild(n.children || [])}
            })
        }
        context.setTags(addChild(context.tags))
    }

    const handleAddRoot = () => {
        const newTag = {name: 'New tag', color: defaultColor, children: []}
        context.setTags([...context.tags, newTag])
    }

    const handleSaveEdit = () => {
        if (!currentTag) return
        context.updateTag(currentTag)
        setShowModal(false)
    }

    return <div>
        <div className="h5 my-3">Tags</div>

        <div className="panel py-2">
            <div className="pt-2">
                <Button onClick={handleAddRoot} size="sm" className="me-2">Add new</Button>
                <Button onClick={() => {
                    context.getAllTaggedContent({landId: context.currentLand.id})
                }} size="sm" className="me-2">View tagged content</Button>
            </div>

            <hr/>

            <div className="TagExplorer-tagTree">
                <TagTree
                    tags={flatTags}
                    onReorder={handleReorder}
                    onEdit={handleEdit}
                    onDelete={handleDelete}
                    onAddChild={handleAddChild}
                />
            </div>
        </div>

        <Modal show={showModal} onHide={handleClose} size="sm">
            <Modal.Header closeButton>
                <Modal.Title>Edit tag</Modal.Title>
            </Modal.Header>

            <Modal.Body>
                <div className="mb-3">
                    <label className="form-label">Name</label>
                    <input
                        type="text"
                        className="form-control"
                        value={currentTag?.name || ''}
                        onChange={(e) => setCurrentTag({...currentTag, name: e.target.value})}
                    />
                </div>
                <div className="mb-3">
                    <label className="form-label">Color</label>
                    <div className="d-flex align-items-center gap-2">
                        <input
                            type="color"
                            value={currentTag?.color || defaultColor}
                            onChange={(e) => setCurrentTag({...currentTag, color: e.target.value})}
                            style={{width: 48, height: 36, border: 'none', padding: 0}}
                        />
                        <span>{currentTag?.color || defaultColor}</span>
                    </div>
                </div>
            </Modal.Body>

            <Modal.Footer>
                <Button variant="secondary" onClick={handleClose}>Close</Button>
                <Button variant="primary" onClick={handleSaveEdit}>Save</Button>
            </Modal.Footer>
        </Modal>
    </div>
}

export default TagExplorer
