import { Outlet } from 'react-router-dom'
import Header from '../components/Header'
import Sidebar from '../components/Sidebar'
import './MainLayout.css'

export default function MainLayout() {
  return (
    <div className="App">
      <div className="App-header">
        <Header />
      </div>
      <div className="App-sidebar">
        <Sidebar />
      </div>
      <div className="App-view">
        <Outlet />
      </div>
    </div>
  )
}
