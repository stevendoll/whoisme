# t12n.ai Design Tokens

## Colors
| Token       | Value                     | Usage                        |
|-------------|---------------------------|------------------------------|
| background  | `#054f59`                 | Page background (dark teal)  |
| white       | `#f5f0e8`                 | Primary text (warm cream)    |
| cream       | `#ede8de`                 | Secondary cream              |
| accent      | `#4db6ac`                 | Teal accent, links, input text |
| accent-bright | `#66d4c8`               | Hover states                 |
| muted       | `#4a4a4a`                 | Muted text                   |
| border      | `rgba(245,240,232,0.12)`  | Subtle borders               |
| yellow      | `#FFFF33`                 | Play button                  |
| yellow-hover | `#FFFF66`                | Play button hover            |
| red         | `#ff6b6b`                 | Mic recording, error states  |

## Fonts
| Font             | Weights     | Usage                         |
|------------------|-------------|-------------------------------|
| Instrument Serif | 400 (reg + italic) | Headings, VoiceBox input |
| DM Mono          | 300, 400, 500 | Body, labels, buttons      |

Google Fonts URL: `https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Mono:wght@300;400;500&display=swap`

## Images & Assets
| File                          | Usage                     | Notes              |
|-------------------------------|---------------------------|--------------------|
| `/assets/t12n-ai-rabbit.png`  | Hero logo                 | ~160×160px         |
| `/assets/t12n-ai-name.png`    | Nav logotype              | 19px height        |
| `/favicon.png`                | Browser tab icon          |                    |

## Backgrounds
| Layer         | Description                                                        |
|---------------|--------------------------------------------------------------------|
| Base          | `#054f59` solid dark teal                                          |
| Grain overlay | SVG fractalNoise (baseFrequency 0.9, 4 octaves) at opacity 0.35, fixed, z-index 100 |

## Animations
| Name        | Description                                               |
|-------------|-----------------------------------------------------------|
| `fadeUp`    | opacity 0→1, translateY 24px→0                           |
| `micPulse`  | opacity 1→0.4→1 loop (recording state)                   |
| `heartbeat` | scale + yellow glow pulse (play button idle state)        |

## Custom Cursor
- Dot: 10px teal circle, `mix-blend-difference`
- Ring: 36px circle, `rgba(77,182,172,0.4)` border, lagged follow
