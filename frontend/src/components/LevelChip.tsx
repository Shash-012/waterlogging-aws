import { LEVEL_STYLE, markerSvg, type Level } from './levels'

export function LevelChip({ level }: { level: Level }) {
  return (
    <span className={`wl-chip wl-chip-${level.toLowerCase()}`} style={{ borderColor: LEVEL_STYLE[level].color }}>
      <span className="wl-chip-icon" dangerouslySetInnerHTML={{ __html: markerSvg(level, 12) }} />
      {level}
    </span>
  )
}
