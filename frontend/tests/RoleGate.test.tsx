import { render, screen } from "@testing-library/react"
import { describe, it, expect, beforeEach } from "vitest"
import { RoleGate } from "../src/components/RoleGate"
import { useAuthStore } from "../src/stores/authStore"

describe("RoleGate", () => {
  beforeEach(() => {
    useAuthStore.setState({ role: "analyst" })
  })

  it("renders children if role matches", () => {
    render(<RoleGate requiredRole="analyst"><div>Protected</div></RoleGate>)
    expect(screen.getByText("Protected").parentElement).not.toHaveStyle({ pointerEvents: "none" })
  })

  it("disables children if role does not match", () => {
    render(<RoleGate requiredRole="senior_analyst"><div>Protected</div></RoleGate>)
    expect(screen.getByText("Protected").parentElement).toHaveStyle({ pointerEvents: "none" })
  })

  it("always allows approver", () => {
    useAuthStore.setState({ role: "approver" })
    render(<RoleGate requiredRole="senior_analyst"><div>Protected</div></RoleGate>)
    expect(screen.getByText("Protected").parentElement).not.toHaveStyle({ pointerEvents: "none" })
  })
})
