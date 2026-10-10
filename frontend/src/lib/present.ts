// ?present=1 is the video-recording mode: larger type, no dev controls, and the
// headline replay preloaded. ?event=<event_id> picks a different replay.
// 28 Jun 2024: warnings came hours before the rain (see handoff/a.md). The
// fixtures have no replay for it, so fixtures mode falls back to the first storm.
export const HEADLINE_EVENT = '2024-06-28'

export interface PresentMode {
  present: boolean
  eventId: string | null
}

export function readPresentMode(search: string): PresentMode {
  const params = new URLSearchParams(search)
  const present = params.get('present') === '1'
  return {
    present,
    eventId: params.get('event') ?? (present ? HEADLINE_EVENT : null),
  }
}
