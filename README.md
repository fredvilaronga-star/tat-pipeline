# TAT WaterLine — Dashboard público do pipeline (auto-atualizado)

Gera, **todo dia**, um `index.html` com o **funil completo em board Kanban**: os cards
das companhias por estágio, **clicáveis** para abrir o detalhe (score, frota, quadrante,
propensão, prazo com destaque de vencendo/vencido, nº de toques, última atividade e
risco). Lê direto do **Notion** e publica no **GitHub Pages**.

Mostra **nomes de conta e estágios**, mas **não** inclui **contatos** (pessoas),
**valores** (US$) nem históricos nominais — seguro para uma URL pública `github.io`.
O detalhe confidencial continua só no Notion.

## O que você precisa fazer uma vez (10–15 min)

### 1) Criar a integração do Notion (token)
1. Acesse https://www.notion.so/my-integrations → **New integration**.
2. Nome: `TAT Dashboard`. Tipo: **Internal**. Capabilities: **Read content** **e Insert content**
   (o *Insert* é necessário só uma vez, para a migração de Contatos e Eventos criar as linhas no Notion).
3. Copie o **Internal Integration Secret** (começa com `secret_` / `ntn_`). Guarde.

### 2) Dar acesso das bases à integração
No Notion, abra a página **TAT WaterLine · Pipeline Cockpit** → menu **•••** (canto
superior direito) → **Connections / Conexões** → adicione **TAT Dashboard**.
Isso libera as bases **Contas** e **Interações** para a leitura.

### 3) Criar um repositório DEDICADO no GitHub
Crie um repositório **novo** (ex.: `tat-pipeline`) — **não** use o repositório do
one-pager da Etihad, para não sobrescrever aquele conteúdo. A URL pública ficará
`https://SEU-USUARIO.github.io/tat-pipeline/`.

Suba estes arquivos no repositório (mantendo a pasta `.github/workflows/`):
```
generate_dashboard.py
migrate.py
data_contatos.json
data_eventos.json
.github/workflows/update-dashboard.yml
```

### 4) Cadastrar os segredos no GitHub
No repositório → **Settings → Secrets and variables → Actions → New repository secret**.
Crie os três:

| Nome | Valor |
|---|---|
| `NOTION_TOKEN` | o segredo da integração (passo 1) |
| `CONTAS_DS` | `77949769-ec49-45d5-95fa-111f6f9d64a1` |
| `INTERACOES_DS` | `54d6bc50-22b3-4c9a-9eb9-6a492224bbf8` |
| `CONTATOS_DS` | `af10b604-ea2b-4444-8348-40559259a7e2` |
| `EVENTOS_DS` | `7b0f80d1-2075-4e3c-adeb-f7e28c2c2603` |

> Também conecte a integração `TAT Dashboard` às bases **Contatos** e **Eventos**
> (menu ••• → Connections), igual você fez com Contas e Interações. Sem isso a
> migração não enxerga as bases.

### 5) Ligar o GitHub Pages
**Settings → Pages → Build and deployment → Source: Deploy from a branch →
Branch: `main` / `/ (root)` → Save.**

### 6) Rodar a primeira vez
**Actions → "Atualizar dashboard (diário)" → Run workflow.** Ele gera o `index.html`,
faz commit e o Pages publica. Depois disso roda sozinho **todo dia às 09:00 UTC**
(06:00 de Brasília). Você pode rodar sob demanda a qualquer momento pelo mesmo botão.

## Como funciona
- `migrate.py` roda **uma vez** (é idempotente — se a base já tem linhas, pula) e
  sobe os **48 contatos** e os **16 eventos** dos arquivos JSON para as bases
  **Contatos** e **Eventos** no Notion. Depois disso, **você edita tudo no Notion**
  (adiciona contato, marca "Confirmado", muda data de inscrição) e o dashboard reflete.
- `generate_dashboard.py` lê as quatro bases do Notion via API oficial (Contas,
  Interações, Contatos, Eventos), calcula os agregados e escreve `index.html`. As
  abas do dash: **Pipeline** (funil Kanban clicável com timeline completa), **Contatos**
  (por nível de importância) e **Eventos** (em ordem de data — os próximos primeiro,
  os já realizados no fim, esmaecidos; com aviso de prazo de inscrição vencendo).
- `update-dashboard.yml` roda no cron diário, executa migração + geração e dá push do
  `index.html` (só commita se algo mudou).

## Ajustes fáceis
- **Horário:** mude o `cron` no `.yml` (está em UTC).
- **Janela de "prazo vencendo":** no `.py`, `0 <= delta <= 7` (dias).
- **Cores/《layout:** tudo no fim do `.py`, na função `render()`.

Confidencial · TAT Operating.
