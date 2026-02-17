import { useParams } from 'react-router-dom'
import { ConfigContext } from '../../app/Context'
import LandExplorer from '../../components/LandExplorer/LandExplorer'
import ExpressionExplorer from '../../components/ExpressionExplorer/ExpressionExplorer'

/**
 * LegacyExplorer wraps the original Context-based explorer layout
 * within the new routing structure.
 * The landId is provided by the URL param and the ConfigContext
 * manages the state internally via componentDidMount → initialize().
 */
export default function LegacyExplorer() {
    return (
        <ConfigContext>
            <div style={{
                display: 'grid',
                gridTemplateColumns: '25% 75%',
                height: 'calc(100vh - 60px)',
                overflow: 'hidden',
            }}>
                <aside style={{ overflowY: 'auto', padding: '1rem', borderRight: '1px solid #dee2e6' }}>
                    <LandExplorer />
                </aside>
                <section style={{ overflowY: 'auto', padding: '1rem', position: 'relative' }}>
                    <ExpressionExplorer />
                </section>
            </div>
        </ConfigContext>
    )
}
