# Bria Bowl History — Build Plan

Nov 16, 2026 · @Levi

## Overview

Build a mobile-first, single-page web app that tells the history of our fantasy football league, the Bria Bowl, from 2002 to today. It is Levi's annual "league note" gift to the group. Hand this whole doc to Claude Code as the brief.

The app has two views, both driven by one timeline:

1. **Roster story.** A vertical scrollytelling version of HLTV's roster-over-time chart. People are columns, years run down the page, and the story is told as you scroll.
2. **Friend web.** A ring-based relationship graph that shows how everyone is connected, including people outside the league who linked us together.

**Guiding principles**

- Mobile-first: design at 390px wide, then scale up to desktop. Touch first, hover as a bonus.
- One gesture tells the whole story: scrolling up and down.
- Everything is dripping in interaction detail. No element just appears; everything enters, exits and transforms with intent.
- All content lives in data files, so Levi can edit stories and stats without touching code.
- Static site with no backend, deployed to GitHub Pages.

**Suggested stack** (Claude Code can adjust)

- Vite + TypeScript, no heavy framework (Svelte is fine if it helps with state)
- GSAP + ScrollTrigger for scroll-linked animation and pinning
- d3-force (or hand-rolled layout) for the friend web, rendered in SVG
- GitHub Actions workflow that builds and deploys to GitHub Pages on push to `main`
- Levi doesn't code: include a short README with one-command local preview and how to edit the data files

## Data model

All content lives in `/data` as JSON. Both views read the same files. Fields marked `TODO` are placeholders Levi will fill in.

**`people.json`** — everyone in the story, league member or not

```json
{
  "id": "mike-whiting",
  "name": "Mike Whiting",
  "nickname": null,
  "initials": "MW",
  "role": "member",            // "member" | "outsider"
  "avatar": "avatars/mike-whiting.jpg",  // TODO: Levi supplies; fall back to initials
  "color": "#TODO",             // column color; members only
  "story": "How they came to the league (markdown)",
  "anecdotes": ["TODO"],
  "legacy": "see legacy.json"
}
```

**`roster.json`** — the 12 slots per season (the whiteboard grid)

```json
{ "seasons": { "2011": ["levi", "zaid", "max", "adam", "nate", "toby", "andy", "callan", "dominic", "jared", "stephen", "tim"] } }
```

Seasons 2017 to the current season repeat the 2016 lineup. Generate them in code from a `currentThrough` value so a new season is a one-line change.

**`connections.json`** — edges for the friend web and the path sentences

```json
{ "from": "adam", "to": "mike-whiting", "year": 2011, "how": "class project partners, bonded over wrestling", "type": "class" }
```

Types: `family`, `high-school`, `roommate`, `dorm`, `class`, `frat`, `party`, `friend`.

**`story.json`** — the glass info cards, one or more per year

```json
{ "year": 2014, "title": "A tumultuous season", "body": "markdown", "in": ["jordan", "josh"], "out": ["andy", "sam"], "quote": { "by": "max", "text": "..." } }
```

**`legacy.json`** — Mike's custom legacy rankings (TODO: Levi provides, ideally as a CSV export that a build script converts)

```json
{
  "source": "Mike Whiting's legacy rankings",
  "allTime": [{ "person": "TODO", "rank": 0, "score": 0 }],
  "bySeason": { "2016": [{ "person": "TODO", "rank": 0, "notes": "TODO" }] },
  "champions": { "2011": "TODO" }
}
```

Keep the legacy schema loose until Levi shares Mike's actual format. Build the UI against this placeholder and adapt the loader later.

## Roster data

This is the final slot grid from Levi's research. A slot is a seat in the 12-team league. When someone leaves, their replacement takes the same slot, and that slot continuity is what drives the column animation.

| Slot | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 → now |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Levi | Levi | Levi | Levi | Levi | Levi |
| 2 | Zaid | Zaid | Zaid | Zaid | Zaid | Zaid |
| 3 | Max | Max | Max | Max | Max | Max |
| 4 | Adam | Adam | Adam | Adam | Adam | Adam |
| 5 | Nate | Nate | **Jon** | Jon | Jon | Jon |
| 6 | Toby | Toby | **Ben** | Ben | Ben | **Gabe** |
| 7 | Andy | Andy | Andy | **Josh** | Josh | Josh |
| 8 | Callan | **Mike** | Mike | Mike | Mike | Mike |
| 9 | Dominic | **Kyle** | Kyle | Kyle | Kyle | Kyle |
| 10 | Jared | **Sam** | Sam | **Jordan** | Jordan | Jordan |
| 11 | Stephen | **Dave** | Dave | Dave | Dave | Dave |
| 12 | Tim | Tim | **Stephen** | Stephen | Stephen | **Kalyn** |

Bold = joined that season. No changes in 2015 or from 2016 onward.

**Notable patterns the UI must handle**

- **A returner:** Stephen Rydberg is a founder (slot 11), leaves after 2011, and returns in 2013 in a different slot (12). His avatar leaves the alumni pile and re-enters as a new column. Show a small "returns" badge and connect his two columns visually (e.g. a faint dotted arc).
- **Four constants:** Levi, Zaid, Max and Adam have played every season. Give their column an added bit of flair. Not an icon or something boring…a subtle hue shift or something.

**People**

| Person | Initials | Seasons | Status |
| --- | --- | --- | --- |
| Levi Nellen | LN | 2011–now | Current, founder |
| Zaid Hunitie | ZH | 2011–now | Current, founder |
| Max Christensen | MC | 2011–now | Current, founder |
| Adam Herr | AH | 2011–now | Current, founder |
| Jon Petters | JP | 2013–now | Current |
| Gabe Warneke | GW | 2016–now | Current |
| Josh Susee ("Suze") | JS | 2014–now | Current |
| Mike Whiting | MW | 2012–now | Current |
| Kyle Mont Blanc | KM | 2012–now | Current |
| Jordan Morris | JM | 2014–now | Current |
| Dave Skradski | DS | 2012–now | Current |
| Kalyn Reinardy ("Ginge") | KR | 2016–now | Current |
| Nate Mehlhoff | NM | 2011–2012 | Alumni, founder |
| Toby Bachuber | TB | 2011–2012 | Alumni, founder |
| Tim Comes | TC | 2011–2012 | Alumni, founder |
| Andy Althoff | AA | 2011–2013 | Alumni, founder |
| Callan Curtis | CC | 2011 | Alumni, founder |
| Dominic Morelli | DM | 2011 | Alumni, founder |
| Jared Haldemann | JH | 2011 | Alumni, founder |
| Stephen "Scuba" Rydberg | SR | 2011, 2013–2015 | Alumni, founder, returner |
| Sam Schurman | SS | 2012–2013 | Alumni |
| Ben Rydberg | BR | 2013–2015 | Alumni |

**Outsiders** (in the friend web and story cards, never columns): Dustin Sadnick (Levi's brother), Doug Comes (Tim's brother), Lucas "Luke" Reinardy (Kalyn's older brother), Alex Randall, Alex Hoover, Tim Underhill, Megan Hardie, Kennedy Curtis, "Fish".

## Story content

This is the seed content for `story.json`, taken from Levi's FigJam timeline plus details from our planning chat. Keep Levi's voice; light copy edits only. Every bolded name in a card should be tappable and open that person.

**2002 — Where it starts** Dustin Sadnick (Levi's brother) and Doug Comes (Tim Comes's brother) are freshman roommates at Winona State. Years later, Dustin tells Levi to look out for Tim on his dorm floor.

**2008 — The visit** Max Christensen spends a high school visit weekend in Winona with his "pal" Alex Randall. Fun fact: that weekend eventually brought Tim Underhill (Levi's future roommate), Alex Hoover and Sam Schurman into our sphere.

**2009 — Freshman year**

- Levi's roommate Nate Mehlhoff introduces him to Max and Zaid.
- Max rooms with Jared Haldemann and lives next to Toby Bachuber.
- Max, Zaid and Nate know Stephen Rydberg and his little brother Ben from high school.
- On his brother's instruction, Levi befriends Tim Comes, whose roommate is Lucas Reinardy, older brother of Kalyn.
- The group parties at "Japs", Alex Randall's house. Alex went to high school with Sam Schurman.
- Levi, Max, Zaid, Tim and Nate befriend Megan Hardie, whose dorm neighbor Kennedy Curtis is Callan Curtis's sister.
- Levi befriends Dominic Morelli, a dorm neighbor at Prentiss-Lucas.

**2010** Levi befriends WSU transfer Kyle Mont Blanc through English courses.

**2011 — The league is born**

- Levi convinces high school friend Adam Herr to move to Winona, in with him, Zaid, Callan and Dominic.
- Andy Althoff grew up with Luke Reinardy. When Max, Tim and Nate needed another roommate, Luke brought Andy in.
- The league is named The Quest to the Bria Bowl, "because we are not creative and liked the show The League."
- Founders: Levi, Max, Zaid, Adam, Nate, Tim, Stephen, Toby, Jared, Dom, Cal, Andy.
- Adam meets Mike Whiting as class project partners; both love wrestling.
- Fun fact: Max went to a KFAN fantasy draft party, paid to go, didn't know much football, brought a binder, and threw up at the draft. Toby passed out by round 6.

**2012 — First shake-up**

- Dave Skradski, high school friend of Max, Zaid and Nate, joins WSU.
- Dom moves away, Callan doesn't watch football, and Jared pulls off a hilarious trade on Zaid and is more or less insufferable.
- OUT: Dom, Cal, Jared, Stephen. IN: Mike, Kyle, Dave, Sam.
- Fun fact: Nate really wanted Mike in the league.
- Tim Comes starts a frat; Mike, Jon Petters and Adam join.

**2013**

- Toby isn't interested, Nate is too busy, and Tim doesn't really watch football.
- The Rydbergs are a fairly unanimous pick, as is Petters.
- OUT: Toby, Tim, Nate. IN: Stephen (returns), Ben, Jon.

**2014 — A tumultuous season**

- Interim commissioner Max sends Andy and Sam the exit message. Use the full quote from Levi's FigJam as a pull-quote card, including "I consulted my Small Council".
- Many in the league have met Suze over the years (Levi's high school friend), so he and Jordan join.
- Jordan's way in: Kyle met him through "Fish", a high school friend of Kyle's who lived in the West Campus dorms with Jordan.
- On Jordan being offered a spot, Max: "Personally, I don't want him. That's just me, everybody can have their own opinion."
- Max fleeces Ben Rydberg in a shady trade and pushes it through himself. He is voted out as commissioner and Levi is rightfully reinstated.
- OUT: Andy, Sam. IN: Jordan, Josh.

**2016 — The current era**

- Ben and Stephen "Scuba" Rydberg exit.
- IN: Gabe Warneke (met Zaid through a big marketing project) and Kalyn "Ging” Reinardy (Luke's little sister, always around the group).
- "Many relent this day."

**2017 → now** The lineup hasn't changed. These years are carried by legacy data: champions, rankings and any anecdotes Levi adds per season (TODO).

**Connections to encode** (beyond those above)

- Stephen roomed with Max and Zaid for a couple of years.
- Mike and Jon are frat brothers; Jon came in through Tim's frat.
- Luke Reinardy: Tim's freshman roommate; also lived with Max, Zaid and Nate.
- Josh: Levi's high school friend, a frequent Winona visitor.

## View 1: Roster story

The whole history is one long vertical scroll. Columns are people, time runs down the page, and the story arrives as glass cards over the columns.

**Layout (mobile, 390px)**

- **Header bar (sticky):** up to 12 column headers with circular avatars (about 26px), plus the alumni pile and the Timeline / Web toggle.
- **Column field:** 12 fixed slots. With the dial taking about 60px on the right, each column is about 26px wide. No grid lines.
- **Dial (sticky, right edge):** see the dial section.
- **Glass cards:** float over the columns at their year, with backdrop blur so the column colors glow through.

**Scroll beats**

1. **Opening (2002):** an empty, quiet page. The first card tells the Dustin + Doug story. Two headers fade in: Levi and Tim. Only people who will later join get a header before 2011; outsiders stay in the cards.
2. **Pre-league (2008–2010):** as each future member is met, their avatar pops into the next free header slot with a small spring. The column below is still empty: these are friends, not league members yet.
3. **2011, the league is born:** a beat moment. All 12 columns fill downward together, like liquid poured into tubes, staggered left to right. The "The Quest → Bria Bowl" card appears.
4. **Seasons (2011–2016):** each season is a fixed band of height. Columns keep growing as you scroll. Cards for that year slide in from the side they are pinned to.
5. **Exits:** a column ends with a rounded cap at the end of the person's last season. Their header avatar lifts, shrinks and flies into the alumni pile, which bumps to show it received them.
6. **Entries:** the replacement's column grows from the same slot, starting a new color just below the cap, with a short gap. Their avatar drops into the header slot. Optional: a thin "replaced by" connector between cap and new column.
7. **Returner (Stephen, 2013):** his avatar leaves the alumni pile and travels to slot 12, with a "returns" badge.
8. **Steady era (2017 → now):** the lineup is stable, so compress these years to shorter bands. Cards here show each season's champion and legacy rankings (TODO data).
9. **Finale (now):** the columns end, and continuing to scroll morphs into the friend web (see View 2).

**Alumni pile** On mobile, a stack of overlapping avatars in the header with a "+N" count. Tapping it opens a bottom sheet listing alumni and their years; tapping one opens their person sheet. On desktop, it can sit in the left gutter as a vertical stack.

**Desktop** Same structure, with more room: columns about 72px wide, names shown under avatars, and cards placed beside the columns instead of over them.

## The dial

The time scrubber is a large rotary dial pinned to the right edge, with only its left half visible. Years are printed around the rim, and the current year sits at the 9 o'clock position, pointing at the content.

- **Two-way binding:** scrolling the page turns the dial; spinning the dial scrolls the page. There is one source of truth: scroll progress.
- **Detents:** the dial snaps to each year with a tick. Use `navigator.vibrate(8)` where supported (Android). iOS Safari doesn't support web vibration, so add a visual tick (a notch flash) and an optional soft click sound, muted by default.
- **Momentum:** a fast flick keeps spinning with friction and settles on the nearest year.
- **Tap a year** on the rim to jump there with an eased scroll.
- **Final notch:** past the current season is a network icon. Landing on it triggers the morph into the friend web.
- **Rest state:** while the page is scrolling, shrink the dial to a thin rim (about 24px) to give columns room. It expands to full size (about 60px visible) on touch, with a spring.
- **Gesture conflict:** touches that start on the dial must capture the gesture (`touch-action: none` on the dial, pointer capture), so a spin never scrolls the page. Test this on a real iPhone early; it's the biggest technical risk.
- **Desktop:** drag to spin, the mouse wheel over the dial steps by one year, and arrow keys step when the dial has focus.
- **Era labels:** subtle labels on the rim group years: Before, Founding, Shake-ups, Current era.

## Person column expansion

Tapping a column (or its header avatar) expands that column in place. The other 11 compress into thin colored slivers instead of leaving the screen. This is the chosen direction (option 2); zoom-in and balloon were rejected.

**Open**

1. The tapped column widens to about 75% of the content width over \~450ms with a spring. The others squeeze to 6–8px slivers on either side, keeping their order and colors.
2. The header avatar scales up and morphs into a pinned person header: larger avatar, name, nickname and a collapse icon.
3. The column's color deepens to become the panel background; content fades in with a 40ms stagger.
4. Glass story cards for other people fade out while the column is open.

**Pinned person header** (sticky at the top of the expanded column)

- Avatar, full name, nickname
- Years active, drawn as a mini version of their own column (with gaps for returners)
- All-time legacy rank from Mike's rankings (count-up on open)
- Collapse icon

**Scroll-linked body**

The expanded column still sits on the timeline, so its content follows your scroll:

- **Before they joined:** their "how we met" story and the connection chain that brought them in.
- **Each season they played:** that season's legacy rank and stats (TODO data), plus any anecdote tied to that year.
- **Their exit (alumni):** why they left, and a "Replaced by → \[person\]" link that switches to that person.
- **Present (current members):** career summary and favorite anecdotes.

Alumni panels use a desaturated version of their color.

**Switch person**

- Tap any sliver: the expansion slides across to that slot. Widths animate together, so it reads as one continuous motion rather than close-then-open.
- Swipe left or right on the expanded panel to move to the neighboring slot.
- The pinned header crossfades; the avatar slides in from the direction of travel.
- The scroll position stays the same, so you see the new person at the same year.

**Close**

- Tap the collapse icon, tap the same column's header again, or pinch inward.
- The reverse of opening: content fades out first, then the slivers spring back to full width and the header morphs back into the small avatar.

**Haptics:** a light tick on open, switch and close (Android).

## View 2: Friend web

The friend web is a ring-based graph, not a free-floating physics web, which gets tangled and jittery on a phone.

**Getting there**

- **Story way:** scrolling past the final season (or landing on the dial's network notch) collapses the current 12 columns upward into their avatars. Those avatars glide into the inner ring, alumni drift in from the pile to the middle ring, and outsiders fade in on the outer ring. Connection lines draw in last. About 1.2s total.
- **Direct way:** a two-option "Timeline / Web" toggle in the header plays the same morph forward or in reverse.
- No bottom tab bar: the dial and bottom sheets already own that space.

**Default state**

- The center is the most-connected person, computed from `connections.json` (degree centrality, tie-break by betweenness). Show a caption like "The person holding this league together."
- Inner ring: current members. Middle ring: alumni. Outer ring: outsiders (Dustin, Doug, Luke, Fish, Alex Randall, etc.).
- Faint lines show all connections, colored by type (family, school, roommate, frat...).

**Tap a person → re-center**

- They glide to the center (\~600ms); everyone else re-sorts into rings by degrees of separation from them: ring 1 = direct connections, ring 2 = two steps away, and so on.
- The rings now mean distance, not status. A small label shows the mode: "Distance from Mike."

**Tap someone on a ring → path**

- The shortest path from the center to them lights up; every other line dims.
- Each link shows its "how" label ("wrestling class", "high school").
- A bottom strip reads it as a sentence: *Mike → Adam (wrestling class) → Levi (high school) → Max (Nate's friend from Lakeville)*.

**Open and reset**

- Tap the center person to open their person sheet (same content as the expanded column, presented as a bottom sheet).
- A Home button returns to the default center and status rings.
- Pinch to zoom, drag to pan.

**Desktop:** hover previews the path; click commits.

## Motion, mobile and accessibility

Motion is the product here, so tokenize it and use the tokens everywhere.

| Token | Value | Used for |
| --- | --- | --- |
| `--dur-micro` | 120ms | taps, ticks, badge pops |
| `--dur-ui` | 280ms | cards, header avatar moves |
| `--dur-expand` | 450ms | column open, close, switch |
| `--dur-morph` | 1200ms | timeline ↔ web transition |
| `--ease-out` | cubic-bezier(0.2, 0.8, 0.2, 1) | entries |
| `--ease-in-out` | cubic-bezier(0.65, 0, 0.35, 1) | morphs |
| spring | stiffness \~300, damping \~28 | avatars, dial, slivers |

**Interaction details to include**

- Avatars entering the header: scale 0.6 → 1 with an overshoot spring, plus a soft glow in their column color.
- Column fill: a slight liquid wobble at the growing edge.
- Exit cap: the column end rounds off with a brief pulse before the avatar flies to the alumni pile.
- Glass cards: 16px backdrop blur, 1px light border, enter with 12px of travel plus a fade, and parallax slightly slower than the scroll.
- Pressed states on everything tappable: scale 0.96 for 120ms.
- Count-ups for stats and ranks when they enter the viewport.

**Mobile-first rules**

- Design at 390×844; test down to 360px wide.
- Touch targets at least 44px. Columns are narrower than that, so the tap target extends across the column's full height and the header avatar.
- Respect safe areas (notch, home indicator).
- Aim for 60fps: animate only transform and opacity, avoid layout thrash, and use SVG or canvas for the web.

**Accessibility**

- Full keyboard support on desktop (tab through columns, Enter to expand, Esc to close).
- Colors must keep text contrast at least 4.5:1 on glass cards in light and dark mode.

## Build phases and open questions

1. **Data + skeleton:** project setup, the JSON files filled from this doc, GitHub Pages deploy working, and a plain static roster chart.
2. **Scroll story:** scroll beats, column growth, exits and entries, alumni pile, glass cards.
3. **Dial:** two-way binding, detents, momentum, gesture capture tested on iPhone.
4. **Column expansion:** slivers, pinned header, scroll-linked body, switching, closing.
5. **Friend web:** rings, re-centering, path sentences, timeline ↔ web morph.
6. **Polish:** motion tokens everywhere, reduced motion, accessibility, performance pass.

**Placeholders Levi will provide**

- [ ] Mike's legacy rankings (format TBD; a CSV export is ideal)
- [ ] Champion for each season, 2011 to now
- [ ] Avatars for every person (photos or illustrations), square, at least 256px
- [ ] A color per member
- [ ] Extra anecdotes per person and per season

**Open questions**

- [ ] Confirmed: slot 4 is Adam Herr. The "Andy" label on the whiteboard was a slip.
- [ ] Outsiders will eventually get photos, Levi to provide.
