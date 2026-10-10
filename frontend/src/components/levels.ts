import type { SnapshotHotspot } from '../types/contract'

export type Level = SnapshotHotspot['level']

// Contract: LOW grey, WATCH amber, HIGH orange, CRITICAL red, each with its own shape
// so colour is never the only signal.
export const LEVEL_STYLE: Record<
  Level,
  { color: string; shape: 'circle' | 'triangle' | 'square' | 'diamond' }
> = {
  LOW: { color: '#8a8f98', shape: 'circle' },
  WATCH: { color: '#e0a100', shape: 'triangle' },
  HIGH: { color: '#f06a00', shape: 'square' },
  CRITICAL: { color: '#d7263d', shape: 'diamond' },
}

export function markerSvg(level: Level, size = 22): string {
  const { color, shape } = LEVEL_STYLE[level]
  const s = size
  const body = {
    circle: `<circle cx="${s / 2}" cy="${s / 2}" r="${s / 2 - 2}"/>`,
    triangle: `<polygon points="${s / 2},2 ${s - 2},${s - 2} 2,${s - 2}"/>`,
    square: `<rect x="3" y="3" width="${s - 6}" height="${s - 6}"/>`,
    diamond: `<polygon points="${s / 2},1 ${s - 1},${s / 2} ${s / 2},${s - 1} 1,${s / 2}"/>`,
  }[shape]
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${s}" height="${s}" viewBox="0 0 ${s} ${s}" fill="${color}" stroke="#fff" stroke-width="2" aria-hidden="true">${body}</svg>`
}
