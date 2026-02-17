import React, {Component} from 'react'
import * as landsApi from '../api/landsApi'
import * as expressionsApi from '../api/expressionsApi'
import * as domainsApi from '../api/domainsApi'
import * as tagsApi from '../api/tagsApi'
import client from '../api/client'
import {delay} from "./Util"

export const DEFAULT_RELEVANCE = 0
export const DEFAULT_DEPTH = 2

export const Context = React.createContext()

// Map legacy sort column names to FastAPI V2 field names
const SORT_COLUMN_MAP = {
    'e.id': 'id',
    'e.title': 'title',
    'd.name': 'domain',
    'e.relevance': 'relevance',
    'COUNT(t.id)': 'tag_count',
}

export class ConfigContext extends Component {
    constructor(props) {
        super(props)
        this.initialState = {
            isConnected: false,
            connecting: false,
            connectionError: false,
            isLoadingExpressions: false,
            lands: [],
            currentDomain: null,
            currentDomainTS: null,
            currentLand: null,
            expressions: [],
            currentExpression: null,
            currentExpressionTS: null,
            currentRelevance: DEFAULT_RELEVANCE,
            minRelevance: 0,
            maxRelevance: 0,
            currentDepth: DEFAULT_DEPTH,
            minDepth: 0,
            maxDepth: 0,
            resultCount: 0,
            pageCount: 0,
            currentPage: 1,
            resultsPerPage: 50,
            sortColumn: 'e.id',
            sortOrder: 1,
            tags: [],
            taggedContent: [],
            allTaggedContent: null,
            allTaggedContentTS: null,
            currentTagFilter: null
        }
        this.state = this.initialState
    }

    ts = () => Math.round(window.performance.now())

    componentDidMount() {
        this.initialize()
    }

    /**
     * Initialize connection: load lands from FastAPI V2.
     * Replaces the legacy setDb() SQLite connection.
     */
    initialize = async () => {
        this.setState({connecting: true})
        try {
            const data = await landsApi.getLands({page: 1, pageSize: 100})
            const lands = data.items || data
            this.setState({
                connecting: false,
                isConnected: true,
                lands: lands,
                currentExpression: null,
                tags: [],
                taggedContent: [],
                allTaggedContent: null,
            })
            if (lands.length > 0) {
                this.getLand(lands[0].id)
            }
        } catch (err) {
            console.error('Failed to initialize:', err)
            this.setState({
                isConnected: false,
                connecting: false,
                connectionError: true,
            })
        }
    }

    // Keep setDb as a no-op for backward compatibility with DatabaseLocator
    setDb = () => {
        this.initialize()
    }

    getLand = async (id) => {
        if (id === null) {
            this.setState({
                currentDomain: null,
                currentLand: null,
                expressions: [],
                currentExpression: null,
                currentRelevance: DEFAULT_RELEVANCE,
                currentDepth: DEFAULT_DEPTH,
                resultCount: 0,
                pageCount: 0,
                currentPage: 1,
                tags: [],
                taggedContent: [],
                allTaggedContent: null,
            })
        } else {
            const switchingLand = !(this.state.currentLand && (this.state.currentLand.id === id))
            const currentPage = switchingLand ? 1 : this.state.currentPage

            try {
                const land = await landsApi.getLand(id)
                // Map FastAPI response fields to legacy format
                const expressionCount = land.expression_count || land.expressionCount || 0
                const mappedLand = {
                    ...land,
                    name: land.name || land.title,
                    expressionCount: expressionCount,
                }

                console.log(`Loaded land #${id}`)
                this.setState({
                    currentDomain: null,
                    currentLand: mappedLand,
                    currentExpression: null,
                    resultCount: expressionCount,
                    pageCount: Math.ceil(expressionCount / this.state.resultsPerPage),
                    currentPage: currentPage,
                })

                if (switchingLand) {
                    this.setState({
                        currentRelevance: DEFAULT_RELEVANCE,
                        minRelevance: land.min_relevance || land.minRelevance || 0,
                        maxRelevance: land.max_relevance || land.maxRelevance || 0,
                        currentDepth: DEFAULT_DEPTH,
                        minDepth: land.min_depth || land.minDepth || 0,
                        maxDepth: land.max_depth || land.maxDepth || 0,
                        taggedContent: [],
                        allTaggedContent: null,
                    })
                    this.getExpressions(id)
                    this.getTags(id)
                }
            } catch (err) {
                console.error(`Failed to load land #${id}:`, err)
            }
        }
    }

    getExpressions = async (landId) => {
        const sortCol = SORT_COLUMN_MAP[this.state.sortColumn] || 'id'
        const order = this.state.sortOrder === 1 ? 'asc' : 'desc'

        const params = {
            min_relevance: this.state.currentRelevance,
            max_depth: this.state.currentDepth,
            page: this.state.currentPage,
            page_size: this.state.resultsPerPage,
            sort: sortCol,
            order: order,
        }

        try {
            const data = await expressionsApi.getExpressions(landId, params)
            // Handle both paginated {items, total} and plain array responses
            const items = data.items || data
            const total = data.total || items.length

            // Map FastAPI field names to legacy field names
            const expressions = items.map(expr => ({
                ...expr,
                domainId: expr.domain_id || expr.domainId,
                domainName: expr.domain_name || expr.domainName,
                tagCount: expr.tag_count || expr.tagCount || 0,
                landId: expr.land_id || expr.landId,
            }))

            console.log(`Loaded expressions from land #${landId}`)
            this.setState({
                isLoadingExpressions: false,
                expressions: expressions,
                resultCount: total,
                pageCount: Math.ceil(total / this.state.resultsPerPage),
            })
        } catch (err) {
            console.error(`Failed to load expressions:`, err)
            this.setState({isLoadingExpressions: false})
        }
    }

    getDomain = async (id) => {
        if (id === null) {
            this.setState({currentDomain: null})
        } else {
            try {
                const domain = await domainsApi.getDomain(id)
                const mappedDomain = {
                    ...domain,
                    expressionCount: domain.expression_count || domain.expressionCount || 0,
                }
                console.log(`Loaded domain #${id}`)
                this.setState({currentDomain: mappedDomain, currentDomainTS: this.ts()})
            } catch (err) {
                console.error(`Failed to load domain #${id}:`, err)
            }
        }
    }

    getExpression = async (id) => {
        if (id === null) {
            this.setState({
                currentExpression: null,
                taggedContent: []
            })
        } else {
            try {
                const expr = await expressionsApi.getExpression(id)
                const mappedExpr = {
                    ...expr,
                    domainId: expr.domain_id || expr.domainId,
                    domainName: expr.domain_name || expr.domainName,
                    tagCount: expr.tag_count || expr.tagCount || 0,
                    landId: expr.land_id || expr.landId,
                    // Images: FastAPI returns array, legacy expects CSV string
                    images: Array.isArray(expr.images)
                        ? (expr.images.length > 0 ? expr.images.map(img => img.url || img).join(',') : null)
                        : expr.images,
                    readable: expr.readable || expr.content || '',
                }
                console.log(`Loaded expression #${id}`)
                this.setState({currentExpression: mappedExpr, currentExpressionTS: this.ts()})
                this.getTaggedContent({expressionId: id})
            } catch (err) {
                console.error(`Failed to load expression #${id}:`, err)
            }
        }
    }

    deleteExpression = async (id) => {
        this.setState({isLoadingExpressions: true})
        try {
            // Handle both single ID and array of IDs
            const ids = Array.isArray(id) ? id : [id]
            for (const exprId of ids) {
                await expressionsApi.deleteExpression(exprId)
            }
            console.log(`Deleted expression(s): ${ids}`)
        } catch (err) {
            console.error(`Failed to delete expression:`, err)
        }
    }

    getPrevExpression = async (id, landId) => {
        const sortCol = SORT_COLUMN_MAP[this.state.sortColumn] || 'id'
        const order = this.state.sortOrder === 1 ? 'asc' : 'desc'

        try {
            const data = await expressionsApi.getNeighbors(id, {
                land_id: landId,
                min_relevance: this.state.currentRelevance,
                max_depth: this.state.currentDepth,
                sort: sortCol,
                order: order,
            })
            const prevId = data.prev_id || data.previous_id || null
            if (prevId !== null) {
                console.log(`Prev expression is #${prevId}`)
            }
            this.getExpression(prevId)
        } catch (err) {
            console.error('Failed to get prev expression:', err)
        }
    }

    getNextExpression = async (id, landId) => {
        const sortCol = SORT_COLUMN_MAP[this.state.sortColumn] || 'id'
        const order = this.state.sortOrder === 1 ? 'asc' : 'desc'

        try {
            const data = await expressionsApi.getNeighbors(id, {
                land_id: landId,
                min_relevance: this.state.currentRelevance,
                max_depth: this.state.currentDepth,
                sort: sortCol,
                order: order,
            })
            const nextId = data.next_id || null
            if (nextId !== null) {
                console.log(`Next expression is #${nextId}`)
            }
            this.getExpression(nextId)
        } catch (err) {
            console.error('Failed to get next expression:', err)
        }
    }

    setCurrentRelevance = value => {
        this.setState({currentRelevance: value}, () => {
            this.setCurrentPage(1)
            this.getLand(this.state.currentLand.id)
        })
    }

    setCurrentDepth = value => {
        this.setState({currentDepth: value}, () => {
            this.getLand(this.state.currentLand.id)
        })
    }

    setCurrentPage = value => {
        this.setState({
            isLoadingExpressions: true,
            currentPage: value
        }, () => {
            delay(400, this.getExpressions, this.state.currentLand.id)
        })
    }

    setResultsPerPage = value => {
        this.setState({resultsPerPage: value}, () => {
            this.getExpressions(this.state.currentLand.id)
        })
    }

    getReadable = async (expressionId) => {
        // In FastAPI V2, readable content is included in getExpression response
        // This triggers a re-fetch of the expression
        try {
            const expr = await expressionsApi.getExpression(expressionId)
            const readable = expr.readable || expr.content || ''
            this.setState(state => {
                const expression = {...state.currentExpression, readable}
                return {
                    currentExpression: expression,
                    currentExpressionTS: this.ts(),
                }
            })
            return readable
        } catch (err) {
            console.error(`Failed to get readable for #${expressionId}:`, err)
        }
    }

    saveReadable = async (expressionId, content) => {
        try {
            await expressionsApi.updateExpression(expressionId, {content})
            console.log(`Saved readable for expression #${expressionId}`)
        } catch (err) {
            console.error(`Failed to save readable:`, err)
        }
    }

    setSortColumn = column => {
        if (this.state.sortColumn === column) {
            this.setState(currentState => {
                return {sortOrder: currentState.sortOrder * -1}
            }, () => {
                this.getExpressions(this.state.currentLand.id)
            })
        } else {
            this.setState({sortColumn: column}, () => {
                this.getExpressions(this.state.currentLand.id)
            })
        }
    }

    setSortOrder = order => {
        this.setState({sortOrder: parseInt(order)}, () => {
            this.getExpressions(this.state.currentLand.id)
        })
    }

    getTags = async (landId) => {
        if (landId === null) {
            this.setState({tags: []})
        } else {
            try {
                const data = await tagsApi.getTags(landId)
                const tags = Array.isArray(data) ? data : (data.items || [])
                console.log(`Loaded tags from land #${landId}`)
                this.setState({tags: tags})
            } catch (err) {
                console.error(`Failed to load tags for land #${landId}:`, err)
                this.setState({tags: []})
            }
        }
    }

    setTags = tags => {
        const tagsHaveChanged = (a, b, d) => {
            if (a.length !== b.length) return true
            return a.some((tag, i) => {
                if (!(i in b)) return true
                if (tag.id !== b[i].id) return true
                if (tag.name !== b[i].name) return true
                const childrenA = tag.children || []
                const childrenB = b[i].children || []
                return tagsHaveChanged(childrenA, childrenB, d + 1)
            })
        }

        if (tagsHaveChanged(this.state.tags, tags, 0)) {
            // Save each tag individually via API
            const saveTags = async (nodes, parentId = null) => {
                for (let i = 0; i < nodes.length; i++) {
                    const tag = nodes[i]
                    if (tag.id) {
                        try {
                            await tagsApi.updateTag(tag.id, {
                                name: tag.name,
                                color: tag.color,
                                parent_id: parentId,
                                position: i,
                            })
                        } catch (err) {
                            console.error(`Failed to update tag #${tag.id}:`, err)
                        }
                    } else {
                        try {
                            const created = await tagsApi.createTag(this.state.currentLand.id, {
                                name: tag.name,
                                color: tag.color,
                                parent_id: parentId,
                                position: i,
                            })
                            tag.id = created.id
                        } catch (err) {
                            console.error('Failed to create tag:', err)
                        }
                    }
                    if (tag.children && tag.children.length > 0) {
                        await saveTags(tag.children, tag.id)
                    }
                }
            }

            saveTags(tags).then(() => {
                console.log("Tags saved")
                this.getTags(this.state.currentLand.id)
                if (this.state.currentExpression !== null) {
                    this.getTaggedContent({expressionId: this.state.currentExpression.id})
                }
            })
        }

        this.setState({tags: tags})
    }

    updateTag = async (tag) => {
        try {
            await tagsApi.updateTag(tag.id, {
                name: tag.name,
                color: tag.color,
            })
            console.log(`Updated tag #${tag.id}`)
            this.getTags(this.state.currentLand.id)
        } catch (err) {
            console.error(`Failed to update tag #${tag.id}:`, err)
        }
    }

    getTaggedContent = async (params) => {
        if (params === null) {
            this.setState({taggedContent: []})
        } else {
            try {
                let data
                if (params.expressionId) {
                    data = await tagsApi.getExpressionTaggedContent(params.expressionId)
                } else if (params.tagId) {
                    data = await tagsApi.getTaggedContent({tag_id: params.tagId})
                } else {
                    data = await tagsApi.getTaggedContent(params)
                }
                const items = Array.isArray(data) ? data : (data.items || [])
                console.log(`Loaded tagged content`)
                this.setState({taggedContent: items})
            } catch (err) {
                console.error('Failed to load tagged content:', err)
            }
        }
    }

    getAllTaggedContent = async (params) => {
        if (params === null) {
            this.setState({allTaggedContent: null})
        } else {
            try {
                let data
                if (params.landId) {
                    data = await tagsApi.getLandTaggedContent(params.landId)
                } else {
                    data = await tagsApi.getTaggedContent(params)
                }
                const items = Array.isArray(data) ? data : (data.items || [])
                console.log('Loaded all tagged content')
                this.setState({allTaggedContent: items, allTaggedContentTS: this.ts()})
            } catch (err) {
                console.error('Failed to load all tagged content:', err)
            }
        }
    }

    deleteTaggedContent = async (taggedContentId, reloadAll = false) => {
        try {
            await tagsApi.deleteTaggedContentV1(taggedContentId)
            if (reloadAll === true) {
                this.getAllTaggedContent({landId: this.state.currentLand.id})
            } else {
                this.getTaggedContent({expressionId: this.state.currentExpression.id})
            }
        } catch (err) {
            console.error(`Failed to delete tagged content #${taggedContentId}:`, err)
        }
    }

    flatTags = (tags, depth) => {
        let out = []
        if (!tags) return out
        tags.forEach(tag => {
            tag.depth = depth
            out.push(tag)
            if (tag.children) {
                out = out.concat(this.flatTags(tag.children, depth + 1))
            }
        })
        return out
    }

    categorizeTaggedContent = tags => {
        let data = []
        this.flatTags(this.state.tags, 0).forEach(tag => {
            let tagContent = {...tag, contents: []}
            tags.forEach(taggedContent => {
                if (taggedContent.tag_id === tag.id) {
                    tagContent.contents.push(taggedContent)
                }
            })
            if (tagContent.contents.length > 0) {
                data.push(tagContent)
            }
        })
        return data
    }

    tagContent = async (tagId, expressionId, text, start, end) => {
        try {
            await tagsApi.createTaggedContentV1({
                tag_id: parseInt(tagId),
                expression_id: parseInt(expressionId),
                text: text,
                start_position: start,
                end_position: end,
            })
            console.log('Saved tagged content')
            this.setState({taggedContent: []}, () => {
                this.getTaggedContent({expressionId: expressionId})
                this.getExpression(expressionId)
            })
        } catch (err) {
            console.error('Failed to create tagged content:', err)
        }
    }

    updateTagContent = async (contentId, tagId, text, reloadAll = false) => {
        try {
            await tagsApi.updateTaggedContentV1(contentId, {
                tag_id: parseInt(tagId),
                text: text,
            })
            console.log(`Updated tag content #${contentId}`)

            let params = {}
            if (this.state.currentTagFilter !== null) {
                params.tagId = this.state.currentTagFilter
            }

            if (reloadAll === true) {
                this.getAllTaggedContent({landId: this.state.currentLand.id, ...params})
            } else {
                this.getTaggedContent({expressionId: this.state.currentExpression.id, ...params})
            }
        } catch (err) {
            console.error(`Failed to update tag content #${contentId}:`, err)
        }
    }

    setTagFilter = tagId => {
        this.setState({currentTagFilter: tagId})
    }

    notFocused = () => document.querySelectorAll('input:focus, textarea:focus').length === 0

    deleteMedia = async (image) => {
        try {
            // Find media ID from the image URL if available
            await client.delete('/v2/media/', {
                data: {
                    expression_id: this.state.currentExpression.id,
                    url: image,
                }
            })
            console.log(`Deleted expression #${this.state.currentExpression.id} media ${image}`)
        } catch (err) {
            console.error('Failed to delete media:', err)
        }
    }

    render() {
        const state = {
            ...this.state,
            setDb: this.setDb,
            initialize: this.initialize,
            getLand: this.getLand,
            getExpressions: this.getExpressions,
            getDomain: this.getDomain,
            getExpression: this.getExpression,
            deleteExpression: this.deleteExpression,
            getPrevExpression: this.getPrevExpression,
            getNextExpression: this.getNextExpression,
            setCurrentRelevance: this.setCurrentRelevance,
            setCurrentDepth: this.setCurrentDepth,
            setCurrentPage: this.setCurrentPage,
            setResultsPerPage: this.setResultsPerPage,
            getReadable: this.getReadable,
            saveReadable: this.saveReadable,
            setSortColumn: this.setSortColumn,
            setSortOrder: this.setSortOrder,
            getTags: this.getTags,
            setTags: this.setTags,
            updateTag: this.updateTag,
            getTaggedContent: this.getTaggedContent,
            getAllTaggedContent: this.getAllTaggedContent,
            tagContent: this.tagContent,
            updateTagContent: this.updateTagContent,
            flatTags: this.flatTags,
            deleteTaggedContent: this.deleteTaggedContent,
            categorizeTaggedContent: this.categorizeTaggedContent,
            notFocused: this.notFocused,
            setTagFilter: this.setTagFilter,
            deleteMedia: this.deleteMedia,
        }
        return (
            <Context.Provider value={state}>
                {this.props.children}
            </Context.Provider>
        )
    }
}
