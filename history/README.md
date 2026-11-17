# Bria Bowl History

The story of the league from 2002 to now, as a scroll. Live at https://hodaeg.github.io/qttbb/

## See it on your computer

You need Node.js installed. Then, from this `history` folder:

```
npm install
npm run dev
```

Open the address it prints (usually http://localhost:5173). Changes you save show up straight away.

## Edit the story (no code)

Everything you read on the site lives in `content/`:

| File | What's in it |
|---|---|
| `people.json` | Everyone in the story: name, nickname, initials, colour, avatar, their story and anecdotes |
| `roster.json` | Who held each of the 12 slots each season |
| `story.json` | The cards you scroll past, in order |
| `connections.json` | Who knows whom and how (the friend web) |
| `legacy-manual.json` | Champions and sackos for 2011-2018, which have to be typed in |

Tips:
- To make a name tappable inside a card, write it as `[[person-id|Name to show]]`, for example `[[max-christensen|Max]]`. The id is the `id` in `people.json`.
- **New season, same 12 people:** raise `currentThrough` in `roster.json`.
- **Someone leaves:** add that season to `roster.json` with the full list of 12, putting the new person in the same position as the one they replace, and add `in` / `out` to that season's card in `story.json`.
- **Avatars:** put a square image (256px or larger) in `public/avatars/` and set `"avatar": "avatars/the-file.jpg"` on the person. Without one, initials are shown.
- Run `npm run validate` to check your edits make sense (it catches misspelled ids and seasons that don't add up to 12).

Stats (legacy rank, records, champions from 2019 on) are not typed in. They come from the league data in this repo and update on their own.

## Look and feel

Colours, fonts and animation timings are all in `src/styles/tokens.css`.

## Publishing

Pushing to `main` rebuilds and publishes the site automatically (`.github/workflows/pages.yml`). It also republishes after each daily data refresh.
