import { Outlet } from 'react-router-dom'
import Header from '../components/Header'
import Sidebar from '../components/Sidebar'
import './MainLayout.css'

export default function MainLayout({ hideSidebar }) {
  return (
    <div className={hideSidebar ? 'App App-no-sidebar' : 'App'}>
      <div className="App-header">
        <Header />
      </div>
      {!hideSidebar && (
        <div className="App-sidebar">
          <Sidebar />
        </div>
      )}
      <div className="App-view">
        <Outlet />
      </div>
    </div>
  )
}
