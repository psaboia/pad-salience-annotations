# Plano: Renomear "Experiment" para "Study"

## Motivação

O termo "Experiment" sugere testar hipóteses científicas, mas o sistema é na verdade uma **coleta estruturada de dados** por especialistas. O termo "Study" é mais apropriado porque:

- Coerente com "Specialist" (especialistas participam de studies, não jobs)
- Contexto acadêmico do projeto PAD (Notre Dame)
- Propósito de pesquisa, não produção comercial

---

## Escopo Total

| Categoria | Arquivos | Ocorrências |
|-----------|----------|-------------|
| Documentação | 4 | ~170 |
| Migrations/DB | 1 | ~40 |
| Backend Python | 8 | ~280 |
| Frontend HTML | 7 | ~51 |
| **Total** | **20** | **~541** |

---

## Etapa 1: Migração do Banco de Dados

**Arquivo:** `migrations/005_rename_experiment_to_study.sql`

```sql
-- Renomear tabelas
ALTER TABLE experiments RENAME TO studies;
ALTER TABLE experiment_samples RENAME TO study_samples;

-- Nota: SQLite não suporta renomear colunas diretamente em versões antigas
-- Se necessário, recriar tabelas com novos nomes de colunas

-- Para assignments, renomear referência
-- experiment_id permanece por compatibilidade ou recriar tabela

INSERT OR IGNORE INTO migrations (version) VALUES ('005_rename_experiment_to_study');
```

**Considerações:**
- SQLite tem limitações para ALTER TABLE
- Pode ser necessário recriar tabelas para renomear colunas
- Fazer backup antes de executar

---

## Etapa 2: Backend - Models

**Arquivo:** `app/models/experiments.py` → `app/models/studies.py`

| Antes | Depois |
|-------|--------|
| `ExperimentCreate` | `StudyCreate` |
| `ExperimentUpdate` | `StudyUpdate` |
| `ExperimentResponse` | `StudyResponse` |
| `ExperimentWithSamples` | `StudyWithSamples` |
| `SampleInExperiment` | `SampleInStudy` |

**Arquivo:** `app/models/__init__.py`
- Atualizar imports e exports

---

## Etapa 3: Backend - Database Functions

**Arquivo:** `app/database.py`

| Antes | Depois |
|-------|--------|
| `create_experiment()` | `create_study()` |
| `get_experiment_by_id()` | `get_study_by_id()` |
| `get_all_experiments()` | `get_all_studies()` |
| `update_experiment_status()` | `update_study_status()` |
| `add_samples_to_experiment()` | `add_samples_to_study()` |
| `get_experiment_samples()` | `get_study_samples()` |
| `get_experiment_assignments()` | `get_study_assignments()` |
| `get_experiment_progress()` | `get_study_progress()` |

- Atualizar queries SQL (nomes de tabelas)
- Atualizar variáveis internas

---

## Etapa 4: Backend - Routers

**Arquivo:** `app/routers/admin.py`

| Antes | Depois |
|-------|--------|
| `/experiments` | `/studies` |
| `/experiments/{experiment_id}` | `/studies/{study_id}` |
| `/experiments/{experiment_id}/samples` | `/studies/{study_id}/samples` |
| `/experiments/{experiment_id}/assignments` | `/studies/{study_id}/assignments` |
| `/experiments/{experiment_id}/activate` | `/studies/{study_id}/activate` |
| `/experiments/{experiment_id}/pause` | `/studies/{study_id}/pause` |
| `/experiments/{experiment_id}/resume` | `/studies/{study_id}/resume` |
| `/experiments/{experiment_id}/progress` | `/studies/{study_id}/progress` |

**Arquivo:** `app/routers/specialist.py`

| Antes | Depois |
|-------|--------|
| `/experiments` | `/studies` |
| `/experiments/{experiment_id}/start` | `/studies/{study_id}/start` |

---

## Etapa 5: Backend - Main App

**Arquivo:** `app/main.py`

| Antes | Depois |
|-------|--------|
| `/admin/experiments/new` | `/admin/studies/new` |
| `/admin/experiments/{experiment_id}` | `/admin/studies/{study_id}` |
| `/admin/experiments/{experiment_id}/progress` | `/admin/studies/{study_id}/progress` |
| `/annotate/{experiment_id}` | `/annotate/{study_id}` |

---

## Etapa 6: Frontend - Renomear Arquivos

| Antes | Depois |
|-------|--------|
| `admin/experiment_detail.html` | `admin/study_detail.html` |
| `admin/experiment_new.html` | `admin/study_new.html` |
| `admin/experiment_progress.html` | `admin/study_progress.html` |

---

## Etapa 7: Frontend - Atualizar Conteúdo

### Todos os templates admin:
- Atualizar links de navegação
- Atualizar URLs de API (`/api/admin/experiments` → `/api/admin/studies`)
- Atualizar variáveis JavaScript
- Atualizar textos visíveis ("Experiment" → "Study")

### Templates específicos:

**dashboard.html:**
- "Experiments" → "Studies" no título da seção
- CSS classes `.experiment-*` → `.study-*`
- Funções JS: `loadExperiments()` → `loadStudies()`

**study_new.html (ex experiment_new.html):**
- Título: "Create New Study"
- Função: `createExperiment()` → `createStudy()`

**study_detail.html (ex experiment_detail.html):**
- Título da página
- Funções: `loadExperiment()` → `loadStudy()`
- Funções: `activateExperiment()` → `activateStudy()`
- etc.

**specialist/dashboard.html:**
- "My Experiments" → "My Studies"
- Funções JS correspondentes

**specialist/annotate.html:**
- Mensagens de conclusão
- Título da página

---

## Etapa 8: Documentação

### Renomear arquivo:
`docs/experiment-system.md` → `docs/study-system.md`

### Atualizar conteúdo:
- `README.md` - todas as referências
- `docs/study-system.md` - todo o documento
- `docs/requirements.md` - referências
- `docs/feedback-questionnaire.md` - referências

---

## Ordem de Execução

1. **Backup do banco de dados**
2. **Migração do banco** (Etapa 1)
3. **Backend models** (Etapa 2)
4. **Backend database.py** (Etapa 3)
5. **Backend routers** (Etapa 4)
6. **Backend main.py** (Etapa 5)
7. **Frontend - renomear arquivos** (Etapa 6)
8. **Frontend - atualizar conteúdo** (Etapa 7)
9. **Documentação** (Etapa 8)
10. **Testar tudo**

---

## Verificação

- [ ] Servidor inicia sem erros
- [ ] Admin consegue criar novo study
- [ ] Admin consegue adicionar samples ao study
- [ ] Admin consegue adicionar specialists ao study
- [ ] Admin consegue ativar study
- [ ] Specialist vê studies atribuídos
- [ ] Specialist consegue anotar
- [ ] Progresso é rastreado corretamente
- [ ] Dashboard mostra studies corretamente
- [ ] Documentação está atualizada

---

## Notas

- Manter compatibilidade com dados existentes
- SQLite pode requerer recriar tabelas para renomear colunas
- Considerar manter endpoints antigos temporariamente (redirect)
- Atualizar testes se existirem

---

**Criado em:** 2025-01-17
**Status:** Pendente
