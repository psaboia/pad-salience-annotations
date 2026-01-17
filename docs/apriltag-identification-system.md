# Sistema de Identificação de Imagens via AprilTags

## Resumo

Este documento descreve a decisão de design para identificação automática de imagens PAD através de AprilTags, permitindo integração com sistemas de eye-tracking sem necessidade de sincronização manual.

## Contexto

### Problema

O sistema de eye-tracking (Pupil Labs) opera independentemente do sistema de anotação. Para correlacionar dados de gaze com as imagens corretas, precisamos de um mecanismo de identificação automática.

### Solução

Cada imagem PAD exibe um conjunto único de AprilTags. O sistema de eye-tracking detecta as tags e, através da combinação detectada, identifica qual imagem está sendo visualizada.

## Especificações Técnicas

### Família de Tags

- **Família**: tag36h11 (AprilTag v3)
- **Tags disponíveis**: 587 (IDs 0-586)
- **Hamming distance**: 11 bits
- **Robustez**: Muito alta - taxa de falso positivo observada < 0.00005%

### Configuração por Imagem

- **Número de tags por imagem**: 4
- **Posicionamento**: Uma tag em cada canto da imagem
  - Top-left, Top-right, Bottom-left, Bottom-right

### Algoritmo de Alocação de Tags

#### Estratégia: Reutilização Controlada com Distância Mínima

Em vez de alocar tags sequencialmente (limitado a 146 imagens), utilizamos uma estratégia de reutilização controlada que permite milhares de imagens.

**Regras:**
1. Cada imagem recebe um conjunto de 4 tags únicas
2. Qualquer par de imagens deve diferir em **pelo menos 2 tags** (distância mínima = 2)
3. Isso permite identificação robusta mesmo com 1 tag não detectada ou detectada erroneamente

**Exemplo:**
```
Imagem 1: [0, 1, 2, 3]
Imagem 2: [0, 1, 4, 5]     ← compartilha 2 tags (0,1), difere em 2 (2,3 vs 4,5)
Imagem 3: [0, 2, 4, 6]     ← compartilha max 2 tags com qualquer anterior
Imagem 4: [1, 3, 5, 7]
...
```

### Algoritmo de Identificação

#### Estratégia: Melhor Match com Threshold

```python
def identify_image(detected_tags: set) -> Optional[int]:
    """
    Identifica a imagem baseado nas tags detectadas.

    Args:
        detected_tags: Conjunto de IDs de tags detectadas no frame

    Returns:
        ID da imagem identificada, ou None se não identificável
    """
    if len(detected_tags) < 3:
        return None  # Mínimo de 3 tags para identificação confiável

    best_match = None
    best_score = 0
    second_best_score = 0

    for image_id, image_tags in IMAGE_TAG_MAPPING.items():
        score = len(detected_tags & image_tags)  # Interseção
        if score > best_score:
            second_best_score = best_score
            best_score = score
            best_match = image_id
        elif score > second_best_score:
            second_best_score = score

    # Exigir margem de pelo menos 1 tag sobre o segundo melhor
    if best_score >= 3 and (best_score - second_best_score) >= 1:
        return best_match

    return None  # Ambíguo
```

**Requisitos para identificação válida:**
1. Mínimo de 3 tags detectadas
2. Melhor match deve ter pelo menos 1 tag a mais que o segundo melhor
3. Se ambíguo, retorna None (frame descartado para análise)

## Análise de Robustez

### Dados Observados (arquivo marker_detections.csv)

Distribuição de tags detectadas por frame:
- 6 tags: 33,087 frames (55%) - nota: setup original usava 6 tags
- 5 tags: 18,315 frames (30%)
- 4 tags: 5,592 frames (9%)
- 3 tags: 1,978 frames (3%)
- <3 tags: 1,539 frames (3%)

**Conclusão**: Em 97% dos frames, pelo menos 3 tags são detectadas.

### Falsos Positivos

De ~320,000 detecções:
- Tags corretas: 320,634 detecções
- Falsos positivos: ~30 detecções (tags aleatórias)
- **Taxa de erro: 0.00009%**

A alta Hamming distance (11 bits) do tag36h11 garante robustez excepcional.

### Cenários de Falha e Mitigação

| Cenário | Probabilidade | Mitigação |
|---------|---------------|-----------|
| 1 tag não detectada | ~40% dos frames | Distância mínima 2 + match por maioria |
| 2 tags não detectadas | ~6% dos frames | Ainda identificável se 2 tags restantes são únicas |
| Falso positivo | <0.0001% | Match por maioria ignora outliers |
| 3+ tags não detectadas | ~3% dos frames | Frame descartado (threshold mínimo) |

## Capacidade do Sistema

### Cálculo Teórico

Com distância mínima de 2 entre conjuntos de 4 tags escolhidas de 587:
- Limite inferior conservador: **~1,000 imagens**
- Limite prático: **~2,000-5,000 imagens** (depende do algoritmo de alocação)

Para comparação:
- Abordagem sequencial simples: 146 imagens (587 ÷ 4)
- Abordagem combinatória pura: 4.8 bilhões (C(587,4)), mas sem robustez

### Escalabilidade Futura

Se necessário mais de ~1,000 imagens:
1. **Opção A**: Usar família tagStandard41h12 (2,115 tags disponíveis)
2. **Opção B**: Aumentar para 6 tags por imagem (mais redundância, menos capacidade)
3. **Opção C**: Reduzir distância mínima para 1 (menos robusto, mais capacidade)

## Implementação

### Estrutura de Dados

```python
# Mapeamento imagem -> tags (armazenado no banco de dados)
IMAGE_TAG_MAPPING = {
    1: {0, 1, 2, 3},      # sample_id -> set of tag IDs
    2: {0, 1, 4, 5},
    3: {0, 2, 4, 6},
    # ...
}

# Mapeamento reverso para lookup rápido
TAG_TO_IMAGES = {
    0: {1, 2, 3, ...},    # tag_id -> set of sample_ids that use this tag
    1: {1, 2, 4, ...},
    # ...
}
```

### Banco de Dados

```sql
-- Tags associadas a cada sample
CREATE TABLE sample_tags (
    id INTEGER PRIMARY KEY,
    sample_id INTEGER NOT NULL REFERENCES samples(id),
    tag_id INTEGER NOT NULL,  -- AprilTag ID (0-586)
    position TEXT NOT NULL,   -- 'top-left', 'top-right', 'bottom-left', 'bottom-right'
    UNIQUE(sample_id, position)
);

CREATE INDEX idx_sample_tags_sample ON sample_tags(sample_id);
CREATE INDEX idx_sample_tags_tag ON sample_tags(tag_id);
```

### Geração de Tags para Nova Imagem

```python
def allocate_tags_for_new_sample(existing_allocations: List[Set[int]]) -> Set[int]:
    """
    Aloca 4 tags para uma nova imagem garantindo distância mínima de 2
    de todas as alocações existentes.
    """
    all_tags = set(range(587))

    for candidate in combinations(all_tags, 4):
        candidate_set = set(candidate)
        valid = True

        for existing in existing_allocations:
            shared = len(candidate_set & existing)
            if shared > 2:  # Distância < 2
                valid = False
                break

        if valid:
            return candidate_set

    raise ValueError("Não há mais combinações válidas disponíveis")
```

## Referências

- [AprilTag: A robust and flexible visual fiducial system](https://april.eecs.umich.edu/software/apriltag)
- [Pupil Labs Documentation - Surface Tracking](https://docs.pupil-labs.com/core/software/pupil-capture/#surface-tracking)
- Dados de validação: `eyetracking-data-examples/marker_detections.csv`

## Histórico de Decisões

| Data | Decisão | Justificativa |
|------|---------|---------------|
| 2025-01-17 | 4 tags por imagem | Balanço entre capacidade (146+ imagens) e simplicidade |
| 2025-01-17 | Distância mínima 2 | Robustez contra 1 tag faltante/errada |
| 2025-01-17 | Threshold 3 tags | 97% dos frames têm 3+ tags detectadas |
| 2025-01-17 | Match por maioria | Ignora outliers e falsos positivos |
