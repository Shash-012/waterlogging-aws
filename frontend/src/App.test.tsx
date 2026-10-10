import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'
import { getHotspots, getLatestSnapshot, postAlert } from './api/client'

describe('data layer (fixtures)', () => {
  it('loads the 12 fixture hotspots and both snapshots', async () => {
    expect(await getHotspots()).toHaveLength(12)
    expect((await getLatestSnapshot()).city.status).toBe('ALERT')
    expect((await getLatestSnapshot('dry')).city.status).toBe('STANDBY')
  })

  it('fakes POST /alerts and dedupes a repeat send', async () => {
    const req = {
      hotspot_id: 'DL-001',
      run_id: '2026-08-25T07:00:00Z',
      mode: 'replay' as const,
      event_id: '2026-08-25',
      level: 'HIGH' as const,
      risk: 0.368,
      peak_at: '2026-08-25T11:00:00Z',
    }
    const first = await postAlert(req)
    expect(first.duplicate).toBe(false)
    expect(first.text_en.startsWith('[Replay · 25 Aug 2026]')).toBe(true)
    expect((await postAlert(req)).duplicate).toBe(true)
  })
})

describe('App', () => {
  it('shows all 12 hotspots on the map under the rainy sample', async () => {
    render(<App />)
    expect(await screen.findByText(/12 hotspots/)).toBeInTheDocument()
    expect(document.querySelectorAll('.wl-marker')).toHaveLength(12)
    expect(screen.getByTitle('Minto Bridge underpass: HIGH')).toBeInTheDocument()
    expect(screen.getByTestId('city-status')).toHaveTextContent('Alert')
  })

  it('shows an all-grey map under STANDBY for the dry sample', async () => {
    render(<App />)
    await screen.findByText(/12 hotspots/)
    fireEvent.change(screen.getByLabelText(/Sample/), { target: { value: 'dry' } })
    expect(await screen.findByText('Standby')).toBeInTheDocument()
    expect(document.querySelectorAll('.wl-marker-low')).toHaveLength(12)
  })

  it('opens the detail panel from the list and only allows alerts at HIGH or above', async () => {
    render(<App />)
    const list = await screen.findByRole('list', { name: /ranked by risk/ })
    const rows = within(list).getAllByRole('button')
    expect(rows).toHaveLength(12)
    // Rank 1 in the rainy fixture is DL-004 (CRITICAL).
    expect(rows[0]).toHaveTextContent('1')
    expect(rows[0]).toHaveTextContent('CRITICAL')

    fireEvent.click(within(list).getByText('Minto Bridge underpass'))
    expect(screen.getByRole('heading', { name: 'Minto Bridge underpass' })).toBeInTheDocument()
    expect(screen.getByRole('meter', { name: 'Rain trigger' })).toHaveAttribute('aria-valuenow', '0.64')
    expect(screen.getByRole('meter', { name: 'Flood history' })).toHaveAttribute('aria-valuenow', '0.8')
    expect(screen.getByRole('button', { name: 'Send alert' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: 'Send alert' }))
    expect(await screen.findByText(/^Sent: .*Minto Bridge underpass/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    const lowRow = within(screen.getByRole('list', { name: /ranked by risk/ }))
      .getAllByRole('button')
      .find((b) => b.textContent?.includes('LOW'))!
    fireEvent.click(lowRow)
    expect(screen.getByRole('button', { name: 'Send alert' })).toBeDisabled()
  })

  it('updates the pump plan and calls out HIGH spots left without a pump', async () => {
    render(<App />)
    await screen.findByText(/12 hotspots/)
    expect(await screen.findByText(/6 of 6 pumps assigned to 5 spots/)).toBeInTheDocument()
    await waitFor(() => expect(document.querySelectorAll('.wl-marker-pumped')).toHaveLength(5))

    fireEvent.change(screen.getByLabelText('Pumps available'), { target: { value: '2' } })
    const warn = await screen.findByText(/3 HIGH-or-above spots without a pump/)
    expect(warn).toBeInTheDocument()
    await waitFor(() => expect(document.querySelectorAll('.wl-marker-pumped')).toHaveLength(2))
  })

  it('plays the replay end to end with the replay label and report callouts', async () => {
    render(<App />)
    await screen.findByText(/12 hotspots/)
    fireEvent.click(screen.getByRole('button', { name: 'Replay' }))
    expect(await screen.findByText('Replay of 25 Aug 2026')).toBeInTheDocument()
    const scrubber = await screen.findByLabelText('Replay hour')
    expect(screen.getByText(/Hour 1 of 18/)).toBeInTheDocument()

    // Walk every hour: the banner, list and map follow the frame and the label never leaves.
    const statuses: string[] = []
    let firstHigh = -1
    for (let i = 0; i < 18; i++) {
      fireEvent.change(scrubber, { target: { value: String(i) } })
      expect(screen.getByText(new RegExp(`Hour ${i + 1} of 18`))).toBeInTheDocument()
      expect(screen.getByText('Replay of 25 Aug 2026')).toBeInTheDocument()
      expect(document.querySelectorAll('.wl-marker')).toHaveLength(12)
      statuses.push(screen.getByTestId('city-status').textContent ?? '')
      if (firstHigh < 0 && document.querySelector('.wl-marker-high, .wl-marker-critical')) firstHigh = i
    }
    expect(statuses).toContain('Severe')
    // Checklist: the city leaves STANDBY before the first spot reaches HIGH.
    expect(statuses.findIndex((s) => s !== 'Standby')).toBeLessThan(firstHigh)
    const callouts = screen.getByRole('list', { name: 'Flood reports so far' })
    expect(within(callouts).getAllByText(/Flagged HIGH .* before the first report/)).toHaveLength(4)
    expect(document.querySelectorAll('.wl-report-ring')).toHaveLength(4)

    // Play from the end restarts at hour 1 and advances on its own.
    fireEvent.click(screen.getByRole('button', { name: 'Play' }))
    expect(await screen.findByText(/Hour 2 of 18/, {}, { timeout: 2500 })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }))
  })

  it('?present=1 preloads the headline replay with large type and no dev controls', async () => {
    window.history.pushState({}, '', '/?present=1')
    try {
      const { container } = render(<App />)
      expect(await screen.findByText('Replay of 25 Aug 2026')).toBeInTheDocument()
      expect(await screen.findByText(/Hour 1 of 18/)).toBeInTheDocument()
      expect(container.firstChild).toHaveClass('wl-present')
      expect(screen.queryByLabelText(/Sample/)).not.toBeInTheDocument()
      expect(screen.queryByText(/data: fixtures/)).not.toBeInTheDocument()
      // Pumps follow the replay hour.
      expect(screen.getByText('For the replay hour shown')).toBeInTheDocument()
      fireEvent.change(screen.getByLabelText('Replay hour'), { target: { value: '10' } })
      await waitFor(() => expect(document.querySelectorAll('.wl-marker-pumped').length).toBeGreaterThan(0))
    } finally {
      window.history.pushState({}, '', '/')
    }
  })

  it('falls back to the first storm when ?event names an unknown replay', async () => {
    window.history.pushState({}, '', '/?event=1999-01-01')
    try {
      render(<App />)
      expect(await screen.findByText('Replay of 25 Aug 2026')).toBeInTheDocument()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    } finally {
      window.history.pushState({}, '', '/')
    }
  })

  it('switches names to Hindi', async () => {
    render(<App />)
    await screen.findByText(/12 hotspots/)
    fireEvent.click(screen.getByRole('button', { name: 'Show Hindi names' }))
    expect(screen.getByText('मिंटो ब्रिज अंडरपास')).toBeInTheDocument()
  })
})
