# Eye-Tracking Layout Options

## Layout Options (user wants to see 2 and 3)

### Option 2: Tela cheia + sidebar estreita

```
┌────────────────────────────────────────────────────────────────────────────┐
│  [Title + Tools somewhere]                                                 │
├──────────────────────────────────────────────────────────┬─────────────────┤
│                                                          │                 │
│                                                          │  Audio          │
│     [Tag 0]                              [Tag 3]         │  Recording      │
│                                                          │                 │
│                                                          │  ○ 00:00        │
│                  ┌────────────────────┐                  │  [Start Rec]    │
│                  │                    │                  │                 │
│                  │                    │                  ├─────────────────┤
│                  │     PAD Image      │                  │                 │
│                  │                    │                  │  Annotations    │
│                  │                    │                  │  (3)            │
│                  └────────────────────┘                  │                 │
│                                                          │  - Lane D,E     │
│                                                          │  - Lane F       │
│     [Tag 7]                              [Tag 4]         │                 │
│                                                          ├─────────────────┤
│                                                          │                 │
│              (ÁREA TRACKED - só tags + PAD)              │  [DONE]         │
│                                                          │                 │
└──────────────────────────────────────────────────────────┴─────────────────┘
```
- Área tracked ocupa ~75% da largura
- Sidebar estreita (~25%) com controles
- Mais espaço para a imagem do PAD


### Option 3: Tools em cima, tracked no centro, controls embaixo

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           [Tools here]                                     │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│                                                                            │
│        [Tag 0]                                        [Tag 3]              │
│                                                                            │
│                                                                            │
│                     ┌────────────────────────┐                             │
│                     │                        │                             │
│                     │                        │                             │
│                     │       PAD Image        │                             │
│                     │                        │                             │
│                     │                        │                             │
│                     └────────────────────────┘                             │
│                                                                            │
│                                                                            │
│        [Tag 7]                                        [Tag 4]              │
│                                                                            │
│                  (ÁREA TRACKED - só tags + PAD)                            │
│                                                                            │
├────────────────────────────────────────────────────────────────────────────┤
│   ○ Recording: 00:45    │  Annotations: 3  │  [Undo] [Clear]  │   [DONE]   │
└────────────────────────────────────────────────────────────────────────────┘
```
- Layout vertical: tudo empilhado
- Área tracked no centro (largura total)
- Barra de controles compacta embaixo

---

## Tools Position Options (user wants to see 1 and 3)

### Option 1: Barra horizontal acima das tags

```
┌────────────────────────────────────────────────────────────────────────────┐
│                                                                            │
│      [Rectangle] [Polygon] [Undo] [Clear]    Color: ● ● ● ● ●              │
│                                                                            │
├ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┤
│                                                                            │
│        [Tag 0]                                        [Tag 3]              │
│                         ┌──────────────┐                                   │
│                         │  PAD Image   │                                   │
│                         └──────────────┘                                   │
│        [Tag 7]                                        [Tag 4]              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```
- Tools ficam FORA da área tracked
- Linha horizontal logo acima das tags superiores


### Option 3: Barra fixa no topo da página (header)

```
┌────────────────────────────────────────────────────────────────────────────┐
│  PAD Annotation Tool    [Rectangle] [Polygon] [Undo] [Clear]   ● ● ● ● ●   │
│  Eye-tracking Ready                                                        │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│        [Tag 0]                                        [Tag 3]              │
│                         ┌──────────────┐                                   │
│                         │  PAD Image   │                                   │
│                         └──────────────┘                                   │
│        [Tag 7]                                        [Tag 4]              │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```
- Título + Tools juntos no header fixo
- Mais compacto, menos espaço vertical ocupado

---

## Aguardando decisão do usuário

Combinações possíveis:
- Layout 2 + Tools 1
- Layout 2 + Tools 3
- Layout 3 + Tools 1
- Layout 3 + Tools 3
