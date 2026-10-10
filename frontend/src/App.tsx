import { useEffect, useMemo, useState } from 'react'
import { dataSource, getHotspots, getLatestSnapshot } from './api/client'
import { HotspotMap } from './components/HotspotMap'
import type { Hotspot, Snapshot } from './types/contract'

export default function App() {
  const [hotspots, setHotspots] = useState<Hotspot[] | null>(null)
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([getHotspots(), getLatestSnapshot()])
      .then(([h, s]) => {
        setHotspots(h)
        setSnapshot(s)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  const scores = useMemo(
    () => new Map((snapshot?.hotspots ?? []).map((s) => [s.hotspot_id, s])),
    [snapshot],
  )

  return (
    <div className="wl-app">
      <header className="wl-header">
        <h1>Delhi Waterlogging Early Warning</h1>
        <span className="wl-source">Data: {dataSource}</span>
      </header>
      {error && <p role="alert">Could not load data: {error}</p>}
      {!error && !hotspots && <p>Loading…</p>}
      {hotspots && (
        <>
          <p className="wl-count">{hotspots.length} hotspots</p>
          <HotspotMap hotspots={hotspots} scores={scores} />
        </>
      )}
    </div>
  )
}
