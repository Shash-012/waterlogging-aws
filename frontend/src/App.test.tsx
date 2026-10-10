import { fireEvent, render, screen, within } from '@testing-library/react'
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
    expect(await screen.findByRole('status')).toHaveTextContent('Minto Bridge underpass')

    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    const lowRow = within(screen.getByRole('list', { name: /ranked by risk/ }))
      .getAllByRole('button')
      .find((b) => b.textContent?.includes('LOW'))!
    fireEvent.click(lowRow)
    expect(screen.getByRole('button', { name: 'Send alert' })).toBeDisabled()
  })

  it('switches names to Hindi', async () => {
    render(<App />)
    await screen.findByText(/12 hotspots/)
    fireEvent.click(screen.getByRole('button', { name: 'Show Hindi names' }))
    expect(screen.getByText('मिंटो ब्रिज अंडरपास')).toBeInTheDocument()
  })
})
