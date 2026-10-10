import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'
import { getHotspots, getLatestSnapshot } from './api/client'

describe('data layer (fixtures)', () => {
  it('loads the 12 fixture hotspots and the rainy snapshot', async () => {
    expect(await getHotspots()).toHaveLength(12)
    const snap = await getLatestSnapshot()
    expect(snap.city.status).toBe('ALERT')
    expect((await getLatestSnapshot('dry')).city.status).toBe('STANDBY')
  })
})

describe('App', () => {
  it('shows all 12 hotspots on the map', async () => {
    render(<App />)
    expect(await screen.findByText('12 hotspots')).toBeInTheDocument()
    expect(document.querySelectorAll('.wl-marker')).toHaveLength(12)
    expect(screen.getByTitle('Minto Bridge underpass: HIGH')).toBeInTheDocument()
  })
})
