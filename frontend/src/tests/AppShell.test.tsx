import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import App from '../App'

describe('App Shell', () => {
  it('renders the sidebar with all navigation links', () => {
    render(<App />)

    expect(screen.getByText('SOC Triager')).toBeInTheDocument()
    expect(screen.getByText('Alert Queue')).toBeInTheDocument()
    expect(screen.getByText('Incidents')).toBeInTheDocument()
    expect(screen.getByText('MITRE Navigator')).toBeInTheDocument()
    expect(screen.getByText('Ops Metrics')).toBeInTheDocument()
    expect(screen.getByText('Playbook Library')).toBeInTheDocument()
    expect(screen.getByText('Settings')).toBeInTheDocument()
  })

  it('renders the top bar with search and dark mode toggle', () => {
    render(<App />)

    expect(screen.getByLabelText('Global entity search')).toBeInTheDocument()
    expect(
      screen.getByLabelText(/switch to (dark|light) mode/i)
    ).toBeInTheDocument()
  })

  it('renders the WebSocket connection pill in disconnected state', () => {
    render(<App />)

    expect(screen.getByText('Disconnected')).toBeInTheDocument()
  })

  it('defaults to the Alert Queue page on load', async () => {
    render(<App />)

    // Lazy-loaded — wait for the content to appear
    await waitFor(() => {
      expect(
        screen.getByText(/real-time security alerts/i)
      ).toBeInTheDocument()
    })
  })
})
