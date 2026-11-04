# Designing for the patient

Someone opening MedSaarthi may be unwell, worried, older, or unsure of their reading. They may also be holding a piece of paper they couldn't understand and feel embarrassed about it. The interface is built around that person.

> **These are design decisions drawn from general health-communication and behaviour-change ideas. None of them has been tested with patients.** Whether they actually lower anxiety or improve understanding is an open question for a user study (see Limitations).

## The rule for playfulness
**Warm around the task, still on the task.** Saarthi waves, the tiles have suns and stars, and a tick pops. But dose text, warnings and the pharmacist check never animate or joke, and Saarthi's face turns attentive when something needs care. A playful tone on a safety message would teach people not to take it seriously.

## What the patient may feel, and what the screen does

| What the patient may feel | Design response | Where |
|---|---|---|
| **"This is intimidating."** Medical software feels cold | A companion called Saarthi ("guide" or "charioteer") speaks in the first person and in short sentences | Speech bubble on every screen |
| **"Am I doing it wrong?"** Shame about not understanding | Problems belong to the tool, never the person: "I can't find how much to take." and "You haven't done anything wrong." | Check screen |
| **Alarm.** Red and warning words raise fear and can make people stop reading | "Held for a pharmacist" in red became a calm amber "Let's check this one". Red is kept for real errors. The next step is always given | Check screen, reasons in `api/server.py` |
| **Overload.** Too much at once when stressed | One step at a time on a visible three-step path. Confidence scores, models and prompts are behind "How sure am I?" and "For evaluators" | Progress path, disclosures |
| **"What does TDS mean?"** Codes exclude people | Codes appear in words computed by code: "3 times a day (written as TDS)". "Oral" becomes "By mouth" | `plain_frequency`, check screen |
| **"Can I trust a computer with this?"** | Their paper sits beside what was read, so they compare instead of having to trust. Saarthi says what it won't do: "I won't guess" | Check screen |
| **Mixing up doses.** Morning and night confused | Four picture tiles, from sunrise to a dark starry night, so times are places with pictures. In translations, code writes the time with its morning or night word | Day plan, `when_line` |
| **Trouble reading** | Pictures carry the day, type starts at 16-18 px, controls are at least 44 px tall, and "Listen" reads the instructions aloud where the device has a voice for that language | Day plan, `ListenButton` |
| **Left out by English** | Words around the plan switch to the chosen language, not only the instructions | `web/src/i18n.ts` |
| **Losing control** | Their own words for their name, "Fit it to my day", a clock choice, and "Forget this visit". Changing times carries a gentle request to check with the pharmacist | Plan and privacy screens |
| **Waiting anxiety** | Saarthi thinks visibly and says what is happening and how long it takes | Loading states |
| **Fear of being watched** | "Your privacy" is one click from every screen and says what is kept in plain words | Privacy screen |

## Encouragement without harm
Ticking off a dose gives a small, satisfying moment, and finishing the day gets one calm line: "That's everything for today."

**Deliberately left out: streaks, points, badges and scores.** Adherence games can make a missed dose feel like failure, push someone to double up to "catch up", or reward taking more. Ticks are for today only, can be undone, and stay in that browser. The app also gives no advice about missed doses, because that is medical advice.

## Accessibility
Bigger text and high contrast are always in the top bar, not buried in settings. Colour never carries meaning alone. Everything works by keyboard and has an accessible name, and all animation stops under `prefers-reduced-motion`. `tests/e2e_web.py` measures every piece of text at 4.5:1 or better, on every screen and in both modes.

## Limitations
- **Not tested with patients.** Nothing here shows that anxiety fell or understanding rose. A small study with older adults and low-literacy readers would be the honest next step.
- **Partly translated.** The plan screen's labels are translated; the start and check screens are English only. A person who reads no English would need help there.
- **Hand-written translations** of the labels and time words need a native-speaker check, like the rest (EVAL section 8).
- **"Listen" depends on the device.** Many computers have no Kannada, Tamil or Telugu voice, and then the button doesn't appear.
- **A friendly tone can over-reassure.** A warm helper may be trusted more than it deserves, so the disclaimer, the "I'm a helper, not a doctor" line and the pharmacist check stay prominent.

## Visual system
Built with the `design-taste-frontend` skill: "Pastel consumer" app style (seed 1248542262), Manrope, one large radius, with a sage ground and teal chosen for this product. The dealt sidebar was dropped because three steps for one person don't need one. The first redesign, "Achromatic ledger", read like a pharmacist's tool and was replaced for this reason.
