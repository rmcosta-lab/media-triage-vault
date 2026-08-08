# Media Triage Vault

Aplicação local para analisar, classificar, revisar e organizar fotos e vídeos. O projeto
extrai metadados, identifica a origem provável dos arquivos, gera miniaturas e permite
planejar a movimentação para pastas de destino.

Tudo é processado na própria máquina: o backend escuta somente em `127.0.0.1`, não usa
APIs externas e não envia arquivos ou metadados para a internet.

## O que a aplicação faz

- examina uma pasta e suas subpastas sem alterar os arquivos de origem;
- identifica imagens, vídeos e arquivos com extensão incorreta;
- extrai metadados com ExifTool e FFmpeg/FFprobe;
- classifica vídeos, fotos de iPhone, ProRAW, arquivos do WhatsApp e screenshots;
- identifica o país da captura por GPS usando uma base geográfica local;
- permite revisar resultados e corrigir classificações manualmente;
- gera relatórios HTML, JSON e CSV;
- cria um plano de movimentação antes de qualquer alteração;
- exige aprovação explícita para executar o plano;
- registra as operações em um diário transacional, com suporte a retomada.

## Pré-requisitos

O alvo principal do MVP é o **Windows 11**. Antes de começar, instale:

- **Python 3.13**;
- **uv**, para instalar e executar o backend;
- **Node.js 20.9 ou superior**;
- **pnpm 11.20.0**;
- **FFmpeg e FFprobe** disponíveis no `PATH`.

O ExifTool para Windows já está incluído em `tools/exiftool/windows-x64/` e não precisa
ser instalado separadamente.

Uma forma de instalar o FFmpeg no Windows é:

```powershell
winget install Gyan.FFmpeg
```

Depois da instalação, feche e abra o terminal novamente e confira:

```powershell
python --version
uv --version
node --version
pnpm --version
ffmpeg -version
ffprobe -version
```

> A primeira instalação das dependências exige internet. Depois disso, a aplicação
> funciona localmente e não faz chamadas externas durante a análise.

## Instalação

No PowerShell, entre na pasta em que o repositório foi clonado e instale o backend:

```powershell
cd C:\caminho\para\media-triage-vault
uv sync
```

Em seguida, instale o frontend:

```powershell
cd frontend
pnpm install
Copy-Item .env.local.example .env.local
cd ..
```

O arquivo `.env.local` configura o frontend para acessar o backend em
`http://127.0.0.1:8000`.

## Como executar pela interface web

Essa é a forma recomendada de usar a aplicação.

### 1. Inicie o backend

Abra um PowerShell na raiz do projeto:

```powershell
cd C:\caminho\para\media-triage-vault
uv run media-organizer serve
```

O backend ficará disponível em `http://127.0.0.1:8000`. Mantenha esse terminal aberto.

### 2. Inicie o frontend

Abra um segundo PowerShell:

```powershell
cd C:\caminho\para\media-triage-vault\frontend
pnpm dev
```

Acesse [http://localhost:3000](http://localhost:3000) no navegador.

### 3. Use a aplicação

Na página inicial:

1. informe o caminho absoluto da pasta que deseja analisar, por exemplo `D:\Fotos`;
2. escolha se as subpastas devem ser incluídas;
3. clique em **Start scan** e acompanhe o progresso;
4. ao terminar, clique em **Classify**;
5. abra **Review files** para revisar filtros, confiança e justificativas;
6. faça correções manuais, se necessário;
7. abra **Plan move** e defina uma pasta de destino para cada grupo;
8. salve os destinos e clique em **Generate plan**;
9. revise todos os itens planejados, conflitos e alertas;
10. clique em **Approve plan** e somente depois em **Execute**.

Até a etapa de execução, a pasta analisada permanece somente para leitura. A aplicação não
sobrescreve arquivos por padrão; colisões bloqueiam a operação.

## Executar uma versão de produção do frontend

Com o backend em execução, gere e inicie o build do frontend:

```powershell
cd C:\caminho\para\media-triage-vault\frontend
pnpm build
pnpm start
```

Depois, acesse [http://localhost:3000](http://localhost:3000).

## Usar pela linha de comando

A interface de linha de comando está disponível como `media-organizer`:

```powershell
uv run media-organizer --help
```

Exemplo de análise de uma pasta:

```powershell
uv run media-organizer scan "D:\Fotos" --recursive --output ".\runtime\reports\scan-001"
```

Esse comando cria `inventory.json` e `errors.log` na pasta informada e persiste o scan no
banco `runtime/database/media_organizer.db`.

Os principais comandos são:

```text
scan          Examina a pasta, detecta tipos e extrai metadados
classify      Classifica os arquivos de um scan existente
override      Altera manualmente o grupo de um arquivo
report        Gera HTML, JSON, CSV, miniaturas e log de erros
destinations  Configura as pastas de destino
plan          Gera o dry run; não move nenhum arquivo
execute       Executa ou retoma o plano após confirmação explícita
serve         Inicia o backend local
```

Consulte as opções de qualquer comando com `--help`, por exemplo:

```powershell
uv run media-organizer report --help
uv run media-organizer plan --help
uv run media-organizer execute --help
```

## Alterar as portas

Para iniciar o backend em outra porta:

```powershell
uv run media-organizer serve --port 8001
```

Nesse caso, altere `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
```

Reinicie o frontend depois da alteração.

## Testes e verificações

Backend, a partir da raiz do repositório:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy backend
uv run pytest
```

Frontend:

```powershell
cd frontend
pnpm exec tsc --noEmit
pnpm lint
pnpm build
```

## Solução de problemas

### O PowerShell bloqueia `pnpm.ps1`

Use o executável `.cmd` sem alterar a política de execução do sistema:

```powershell
pnpm.cmd install
pnpm.cmd dev
```

### FFmpeg ou FFprobe não foi encontrado

Instale o FFmpeg, reabra o terminal e confirme que `ffmpeg -version` e
`ffprobe -version` funcionam. O backend usa esses programas para validar vídeos e gerar
miniaturas.

### O frontend não consegue acessar o backend

Confirme que:

- `uv run media-organizer serve` continua em execução;
- `http://127.0.0.1:8000/openapi.json` abre no navegador;
- `NEXT_PUBLIC_API_BASE_URL` aponta para a mesma porta do backend;
- o frontend foi reiniciado depois de alterar `.env.local`.

### A porta já está em uso

Inicie o backend em outra porta com `--port` e atualize `frontend/.env.local`, conforme a
seção **Alterar as portas**.

## Segurança dos arquivos

Antes de testar com uma coleção importante, use uma cópia pequena ou os arquivos de teste
em `backend/tests/fixtures/`. A análise é somente leitura, mas a etapa **Execute** realmente
move os arquivos aprovados.

As proteções principais são:

- nenhuma movimentação sem plano e confirmação;
- política de colisão padrão `error`, sem sobrescrita silenciosa;
- validação da cópia antes de remover a origem em operações entre volumes;
- diário transacional para retomada de operações interrompidas;
- banco e relatórios armazenados somente em `runtime/`;
- backend acessível apenas pela própria máquina.

## Documentação do projeto

- [Especificação completa](README_media_triage_vault.md)
- [Missão e princípios](specs/mission.md)
- [Stack técnica](specs/tech-stack.md)
- [Roadmap](specs/roadmap.md)
- [Changelog](CHANGELOG.md)

O MVP atual conclui o fluxo completo de scan, classificação, revisão, dry run, aprovação e
movimentação tanto pela interface web quanto pela CLI. O empacotamento como aplicativo
desktop com Tauri permanece como trabalho futuro.
