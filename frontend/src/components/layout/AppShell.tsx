import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { TopBar } from "./TopBar"
import { ToastContainer } from "../ToastContainer"

export function AppShell() {
  return (
    <div style={{ display: "flex", height: "100vh", width: "100vw", overflow: "hidden" }}>
      <Sidebar />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <TopBar />
        <main style={{ flex: 1, overflow: "auto", position: "relative" }}>
          <Outlet />
        </main>
      </div>
      <ToastContainer />
    </div>
  )
}
