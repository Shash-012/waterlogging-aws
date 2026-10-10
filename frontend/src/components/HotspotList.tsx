import type { Hotspot, SnapshotHotspot } from '../types/contract'
import { formatScore, relativePeak } from '../lib/format'
import { LevelChip } from './LevelChip'

export type Lang = 'en' | 'hi'

export interface Row {
  hotspot: Hotspot
  score: SnapshotHotspot
}

interface Props {
  rows: Row[]
  asOf: string
  lang: Lang
  selectedId: string | null
  onSelect: (id: string) => void
  pumpsById?: Map<string, number>
}

export function HotspotList({ rows, asOf, lang, selectedId, onSelect, pumpsById }: Props) {
  return (
    <ol className="wl-list" aria-label="Hotspots ranked by risk">
      {rows.map(({ hotspot, score }) => {
        const pumps = pumpsById?.get(hotspot.hotspot_id) ?? 0
        return (
          <li key={hotspot.hotspot_id}>
            <button
              type="button"
              className="wl-row"
              aria-pressed={selectedId === hotspot.hotspot_id}
              onClick={() => onSelect(hotspot.hotspot_id)}
            >
              <span className="wl-rank">{score.rank}</span>
              <span className="wl-row-name" lang={lang}>
                {lang === 'hi' ? hotspot.name_hi : hotspot.name_en}
              </span>
              <LevelChip level={score.level} />
              <span className="wl-row-risk">risk {formatScore(score.risk)}</span>
              <span className="wl-row-peak">peak {relativePeak(score.peak_at, asOf)}</span>
              {pumps > 0 && (
                <span className="wl-row-pumps">
                  {pumps} pump{pumps > 1 ? 's' : ''}
                </span>
              )}
            </button>
          </li>
        )
      })}
    </ol>
  )
}
