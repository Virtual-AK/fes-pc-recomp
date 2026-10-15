# Message text codes (MSG1 / .BMD)

What is known about the bytes inside message lines. Worked out from the extracted text of a
real NTSC-U disc (167 message files, about 15,600 lines). "Known" means the structure is
confirmed by the data; "Likely" means inferred from the surrounding text and not yet
confirmed in game.

## Structure (known)

- Plain characters are single ASCII bytes (0x20-0x7E), and 0x0A is a line break.
- **Control codes** start with a byte F1-FF. The total length of the code in bytes is
  `2 * (second hex digit of the first byte)`: F1 = 2 bytes, F2 = 4, F3 = 6, F4 = 8, F5 = 10,
  F6 = 12. The second byte is the function number; the rest are parameters (16-bit words).
  Parameters can look like letters (0x49 is `I`), so always treat the whole code as one unit.
- **Two-byte characters** use a first byte 0x80-0xEF followed by one byte (any value, even
  F0-FF). These are font symbols, not ASCII. Example: `80 B2 80 A5 80 B3 80 A5 80 B2 80 B6 80 A5`
  is the word RESERVE in a wide font, where the second byte is the ASCII code plus 0x60 for
  capitals (R = 0x52 -> B2). Other pairs (lowercase, symbols, kana-like glyphs) index the
  game's font and are not decoded yet.
- A line ends with `F1 04` (the tools hide this; `{NOEND}` marks lines without it).

## Codes seen often

| Code | Meaning |
|------|---------|
| `F2 08 FF FF` then `F1 3F` | Start of nearly every line (15,626 of them). Likely: default text style / dialogue start. |
| `F1 0B` | Likely: the player's name ("Hi, {F1 0B}-san"). |
| `F2 03 NN 01` | Likely: insert a game value, number NN (names, levels, item or Persona names, Arcana names). `F2 03 01 01` appears after "level", `F2 03 02 01` after "Persona of the ... Arcana". |
| `F2 02 02 01` ... `F2 02 01 01` | Likely: start and end of a highlighted span (the text between is shown in a different style). |
| `F3 xx ...` (6 bytes) | Likely: speaker / voice / portrait selection (second byte differs per speaker, e.g. 49, 4B). |
| `F4 20 ...` (8 bytes), `F5 1F ...` (10 bytes) | Likely: longer set-up codes at the start of a message (phone calls, text-message style windows). |

## Using this in the text tool

`p3fes_text.py extract` writes every control code as one `{..}` token and every two-byte
character with its pair, for example `{F2 03 02 01}` and `{80 B2 80 A5}`. Edit the plain
characters freely; keep each `{..}` token exactly as it is, and move it with the words it
belongs to if you rearrange a sentence. `p3fes_textcodes.py` lists every code in a folder of
extracted text with examples.
