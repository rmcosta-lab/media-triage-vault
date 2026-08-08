# Local Media Organizer — Especificação Técnica

**Arquivo:** `spec.md`  
**Versão:** 0.1  
**Status:** Draft para início do desenvolvimento  
**Plataforma primária:** Windows 11  
**Execução:** 100% local e offline  
**Hardware-alvo futuro:** NVIDIA GeForce RTX 4090, 24 GB de VRAM, 32 GB de RAM  

---

## 1. Visão do produto

O Local Media Organizer é uma aplicação desktop/local para analisar uma pasta de fotos e vídeos, extrair metadados, classificar os arquivos, apresentar os resultados em uma interface e em um relatório HTML e, somente após confirmação explícita do usuário, mover os arquivos para diretórios de destino definidos por ele.

O sistema deve operar sem enviar arquivos, metadados, coordenadas, miniaturas ou resultados para serviços externos.

A primeira versão será baseada principalmente em:

- tipo real do arquivo;
- extensão;
- nome do arquivo;
- diretório de origem;
- metadados EXIF, XMP e QuickTime;
- dimensões da imagem;
- regras determinísticas e pontuação de confiança.

A análise visual do conteúdo por modelos de inteligência artificial será implementada em uma fase posterior.

---

## 2. Objetivos do MVP

O MVP deverá:

1. Permitir selecionar ou informar uma pasta de origem.
2. Percorrer a pasta de forma recursiva.
3. Identificar imagens, vídeos, arquivos RAW e arquivos não suportados.
4. Extrair metadados de imagens e vídeos.
5. Classificar cada arquivo em um grupo principal.
6. Identificar fotos e vídeos produzidos por um iPhone.
7. Separar fotografias iPhone em RAW e não RAW.
8. Identificar arquivos provavelmente recebidos pelo WhatsApp.
9. Identificar capturas de tela de celular.
10. Identificar o país de captura quando existirem coordenadas GPS.
11. Apresentar os resultados em uma interface local.
12. Gerar relatório HTML, JSON e CSV.
13. Permitir correção manual da classificação.
14. Permitir que o usuário defina um diretório de destino para cada grupo.
15. Gerar uma simulação completa da movimentação antes da execução.
16. Detectar conflitos, arquivos duplicados, falta de espaço e problemas de permissão.
17. Mover os arquivos somente após confirmação explícita.
18. Validar cada movimentação.
19. Registrar arquivos processados, sucessos, falhas e mensagens de erro.
20. Permitir retomar uma operação interrompida sem repetir arquivos já concluídos.

---

## 3. Fora do escopo do MVP

Não fazem parte da primeira versão:

- upload para nuvem;
- uso de APIs externas;
- geocodificação por serviços online;
- reconhecimento facial;
- identificação de pessoas;
- classificação semântica do conteúdo;
- geração automática de álbuns;
- alteração dos metadados originais;
- exclusão definitiva de arquivos;
- deduplicação automática com remoção;
- monitoramento contínuo de uma pasta;
- aplicação móvel;
- processamento distribuído;
- treinamento ou fine-tuning de modelos.

---

## 4. Princípio de classificação multidimensional

Um arquivo não deve possuir apenas uma única informação de classificação.

Exemplo:

```text
arquivo: IMG_1234.MOV
media_kind: video
source_origin: iphone_camera
capture_country: Japan
routing_group: video
```

Outro exemplo:

```text
arquivo: Screenshot_20260730-152000.png
media_kind: image
source_origin: mobile_screenshot
image_format: standard
routing_group: mobile_screenshot
```

As principais dimensões serão:

| Dimensão | Exemplos |
|---|---|
| `media_kind` | `image`, `video`, `unsupported` |
| `source_origin` | `iphone_camera`, `mobile_screenshot`, `whatsapp_received`, `whatsapp_sent`, `other_camera`, `unknown` |
| `image_format` | `raw`, `standard`, `not_applicable` |
| `capture_country_code` | `BR`, `JP`, `FR`, `unknown` |
| `routing_group` | grupo usado para definir a pasta de destino |
| `confidence` | valor entre `0.00` e `1.00` |
| `classification_reasons` | lista de sinais que justificaram a classificação |

Essa estrutura evita perder informações quando um arquivo se enquadra em mais de uma característica.

---

## 5. Grupos principais de roteamento

A configuração padrão utilizará os seguintes grupos:

1. `video`
2. `mobile_screenshot`
3. `whatsapp_received`
4. `iphone_raw`
5. `iphone_photo`
6. `other`

### 5.1 Prioridade padrão

Quando mais de uma regra for aplicável, a prioridade será:

```text
video
  > mobile_screenshot
  > whatsapp_received
  > iphone_raw
  > iphone_photo
  > other
```

Consequências:

- todo vídeo será enviado para o grupo `video`;
- um vídeo recebido pelo WhatsApp continuará contendo `source_origin=whatsapp_received`;
- um vídeo gravado em iPhone continuará contendo `source_origin=iphone_camera`;
- uma captura de tela recebida pelo WhatsApp será roteada para `mobile_screenshot`;
- uma foto RAW produzida por iPhone será roteada para `iphone_raw`.

A prioridade deverá ser configurável em uma versão posterior.

---

## 6. Tipos de arquivo inicialmente suportados

### 6.1 Imagens padrão

```text
.jpg
.jpeg
.heic
.heif
.png
.webp
.tif
.tiff
.bmp
.gif
```

### 6.2 Imagens RAW

```text
.dng
.cr2
.cr3
.nef
.arw
.raf
.rw2
.orf
```

No MVP, somente arquivos RAW identificados como produzidos por iPhone serão roteados para `iphone_raw`. Outros formatos RAW poderão ser registrados como `image_format=raw`, mas serão roteados para `other`.

### 6.3 Vídeos

```text
.mov
.mp4
.m4v
.avi
.mkv
.3gp
.webm
```

### 6.4 Detecção do tipo real

A classificação não deverá depender apenas da extensão.

O sistema deverá combinar:

- extensão;
- MIME type;
- assinatura do arquivo;
- `FileType` retornado pelo ExifTool;
- resultado do FFprobe para arquivos de vídeo.

Arquivos cuja extensão não corresponda ao conteúdo real deverão receber um alerta.

---

## 7. Descoberta de arquivos

O scanner deverá:

- aceitar uma pasta raiz;
- permitir varredura recursiva;
- utilizar `pathlib`;
- não seguir links simbólicos por padrão;
- ignorar arquivos temporários;
- ignorar arquivos de sistema conhecidos;
- evitar acessar as próprias pastas de relatório e destino;
- registrar erros de acesso sem interromper todo o processo;
- processar os arquivos em lotes;
- atualizar o progresso continuamente;
- calcular o tamanho total analisado;
- registrar data de modificação e tamanho do arquivo.

### 7.1 Arquivos ignorados por padrão

Exemplos:

```text
Thumbs.db
desktop.ini
.DS_Store
~$*
*.tmp
*.partial
```

---

## 8. Extração de metadados

### 8.1 Ferramenta principal

Utilizar o ExifTool como ferramenta principal de leitura de metadados.

O executável deverá ser distribuído ou instalado localmente e chamado pelo backend Python.

A extração deverá ser feita em JSON e preferencialmente em lotes, evitando iniciar um novo processo para cada arquivo.

### 8.2 Metadados relevantes

Campos a extrair quando disponíveis:

```text
FileName
Directory
FileType
MIMEType
FileSize
ImageWidth
ImageHeight
Duration
CreateDate
DateTimeOriginal
MediaCreateDate
TrackCreateDate
Make
Model
Software
LensModel
CameraSerialNumber
GPSLatitude
GPSLongitude
GPSPosition
GPSCoordinates
LocationInformation
HandlerDescription
CompressorName
Encoder
Rotation
ProfileDescription
ColorSpace
```

O sistema deverá preservar também um subconjunto do JSON bruto para auditoria.

### 8.3 Ferramentas complementares

- FFprobe para validar e inspecionar vídeo.
- Pillow para imagens tradicionais.
- `pillow-heif` para HEIC e HEIF.
- `rawpy` para leitura e geração de preview de RAW.
- FFmpeg para gerar frames e miniaturas de vídeo.

---

## 9. Regras para identificar vídeos

Um arquivo será classificado como vídeo quando:

- o MIME type iniciar com `video/`; ou
- o ExifTool indicar um tipo de vídeo; ou
- o FFprobe identificar pelo menos um stream de vídeo válido.

Arquivos de vídeo corrompidos deverão continuar no inventário, mas com:

```text
media_kind: video
processing_status: error
error_code: VIDEO_UNREADABLE
```

---

## 10. Regras para identificar conteúdo produzido por iPhone

### 10.1 Alta confiança

Classificar como `iphone_camera` com alta confiança quando:

```text
Make == "Apple"
AND
Model inicia com "iPhone"
```

Exemplo:

```text
Make: Apple
Model: iPhone 15 Pro Max
```

### 10.2 Vídeos de iPhone

Para vídeos, verificar também metadados QuickTime, incluindo:

- fabricante;
- modelo;
- software;
- encoder;
- chaves Apple;
- localização no formato ISO 6709.

A classificação poderá ser de alta ou média confiança dependendo da quantidade de sinais encontrados.

### 10.3 Sinais insuficientes

O nome `IMG_1234.JPG` ou `IMG_1234.MOV`, isoladamente, não deve ser suficiente para afirmar que o arquivo veio de um iPhone.

Nesse caso:

```text
source_origin: unknown
confidence <= 0.40
```

### 10.4 Arquivos editados ou exportados

Uma fotografia originalmente produzida por iPhone pode perder os campos `Make` e `Model` após edição, exportação ou envio por mensageiro.

O MVP não deverá afirmar origem iPhone somente por semelhança visual ou nome do arquivo.

---

## 11. Regras para separar RAW de iPhone

Uma imagem será classificada como `iphone_raw` quando:

```text
media_kind == image
AND
source_origin == iphone_camera
AND
(FileType == DNG OR extensão == ".dng")
```

Campos específicos de Apple ProRAW poderão ser usados como sinais adicionais, mas não serão obrigatórios quando fabricante, modelo e tipo DNG forem conclusivos.

Arquivos DNG de outras câmeras serão:

```text
image_format: raw
source_origin: other_camera ou unknown
routing_group: other
```

---

## 12. Regras para identificar arquivos do WhatsApp

A identificação será probabilística.

### 12.1 Sinais fortes

Exemplos de nomes:

```regex
^IMG-\d{8}-WA\d+\.(jpg|jpeg|png|heic)$
^VID-\d{8}-WA\d+\.(mp4|mov|m4v)$
^WhatsApp Image .+\.(jpg|jpeg|png)$
^WhatsApp Video .+\.(mp4|mov)$
```

Exemplos de diretórios:

```text
WhatsApp Images
WhatsApp Video
WhatsApp/Media
Media/WhatsApp Images
Media/WhatsApp Video
```

### 12.2 Direção do arquivo

Quando o caminho possuir uma pasta chamada `Sent`, classificar:

```text
source_origin: whatsapp_sent
```

Nos demais casos com sinais suficientes:

```text
source_origin: whatsapp_received
```

Quando não for possível determinar a direção:

```text
source_origin: whatsapp_received
whatsapp_direction: unknown
```

### 12.3 Pontuação sugerida

| Sinal | Pontos |
|---|---:|
| Nome corresponde ao padrão WhatsApp | 0.65 |
| Diretório contém WhatsApp | 0.45 |
| Metadados de câmera ausentes | 0.10 |
| Diretório contém `Sent` | define `whatsapp_sent` |
| Apenas metadados ausentes | não classificar |

Limitar a confiança máxima a `1.00`.

### 12.4 Limitação

Metadados removidos não provam que um arquivo veio do WhatsApp. A ausência de EXIF não deverá ser usada isoladamente.

---

## 13. Regras para identificar captura de tela de celular

Essa será a categoria mais sujeita a falsos positivos na fase sem IA.

### 13.1 Sinais fortes

Nomes como:

```regex
^Screenshot[_ -]
^Screen Shot[_ -]
^Captura de Tela[_ -]
^Screenshot_\d{8}
```

Metadados que indiquem explicitamente screenshot também deverão ser utilizados quando presentes.

### 13.2 Sinais médios

Combinação de:

- formato PNG ou HEIF;
- ausência de dados típicos de câmera;
- orientação vertical;
- proporção compatível com tela de celular;
- resolução conhecida ou próxima de resoluções de smartphones;
- presença de grande quantidade de bordas retangulares e texto, em uma futura heurística OpenCV.

### 13.3 Regra de segurança

Somente dimensões ou orientação vertical não são suficientes.

### 13.4 Confiança

```text
>= 0.85: classificação automática
0.60 a 0.84: classificar e marcar para revisão
< 0.60: manter como other/unknown
```

---

## 14. Identificação do país

### 14.1 Fonte das coordenadas

Extrair coordenadas de:

- EXIF GPS;
- XMP GPS;
- QuickTime GPS;
- localização ISO 6709 em vídeos.

### 14.2 Normalização

Converter todas as coordenadas para:

```text
latitude: float
longitude: float
```

Validar:

```text
-90 <= latitude <= 90
-180 <= longitude <= 180
```

### 14.3 Geocodificação offline

A determinação do país deverá utilizar uma base geográfica local com polígonos de países.

Estratégia recomendada:

1. distribuir um arquivo local `countries.geojson` ou `countries.gpkg`;
2. carregar os polígonos com Shapely;
3. criar índice espacial;
4. executar operação point-in-polygon;
5. retornar código ISO e nome do país.

Exemplo:

```text
GPS: 35.6762, 139.6503
country_code: JP
country_name: Japan
```

### 14.4 Regras

- Sem GPS: retornar `unknown`.
- Coordenada fora de polígonos: retornar `unknown`.
- Não inferir país por fuso horário.
- Não inferir país pelo nome da pasta.
- Não usar endereço IP.
- Não consultar APIs.
- Não mostrar latitude e longitude no relatório por padrão.
- Permitir habilitar coordenadas detalhadas em configuração avançada.

### 14.5 Fronteiras e oceano

Coordenadas próximas a fronteiras ou em áreas marítimas poderão exigir revisão. O sistema deverá guardar o método e a confiança da geocodificação.

---

## 15. Motor de classificação

Cada regra deverá produzir:

```json
{
  "label": "iphone_camera",
  "score": 0.98,
  "reasons": [
    "EXIF Make=Apple",
    "EXIF Model=iPhone 15 Pro Max"
  ]
}
```

A classificação final deverá ser explicável.

### 15.1 Interface sugerida

```python
class ClassificationRule(Protocol):
    name: str

    def evaluate(
        self,
        media: MediaFile,
        metadata: dict
    ) -> RuleResult:
        ...
```

### 15.2 Resultado final

```python
class ClassificationResult:
    media_kind: str
    source_origin: str
    image_format: str
    routing_group: str
    confidence: float
    reasons: list[str]
    requires_review: bool
```

### 15.3 Correção manual

A interface deverá permitir alterar o grupo de um arquivo.

A correção deverá ser registrada separadamente:

```text
automatic_routing_group
manual_routing_group
effective_routing_group
override_timestamp
```

---

## 16. Fluxo funcional

### Etapa 1 — Seleção da origem

O usuário informa ou seleciona a pasta de origem.

O sistema valida:

- existência;
- permissão de leitura;
- quantidade inicial de arquivos;
- se a pasta não coincide com uma pasta de destino ativa.

### Etapa 2 — Análise

O sistema:

1. descobre os arquivos;
2. identifica o tipo;
3. extrai metadados;
4. classifica;
5. extrai GPS;
6. identifica país;
7. gera miniaturas;
8. persiste resultados;
9. atualiza o progresso.

### Etapa 3 — Revisão

O usuário visualiza:

- totais por grupo;
- arquivos com baixa confiança;
- arquivos com erro;
- arquivos sem país;
- miniaturas;
- metadados relevantes;
- justificativas da classificação.

O usuário pode corrigir classificações.

### Etapa 4 — Definição dos destinos

O usuário define um diretório raiz para cada grupo. O nome do
`routing_group` é sempre sanitizado e acrescentado automaticamente como a
primeira subpasta do destino. Se a separação por país estiver habilitada, a
subpasta de país vem depois do grupo:

```text
destination_root / routing_group / [country] / original_file_name
```

Exemplo:

```text
video              -> D:\Midia\video
mobile_screenshot  -> D:\Midia\mobile_screenshot
whatsapp_received  -> D:\Midia\whatsapp_received
iphone_raw         -> D:\Midia\iphone_raw
iphone_photo       -> D:\Midia\iphone_photo
other              -> D:\Midia\other
```

### Etapa 5 — Plano de movimentação

O sistema gera um plano sem modificar arquivos.

O plano deverá validar:

- origem ainda existe;
- destino existe ou pode ser criado;
- permissão de escrita;
- espaço disponível;
- conflitos de nome;
- arquivos duplicados no plano;
- origem e destino iguais;
- alterações ocorridas depois da análise;
- arquivos bloqueados por outro processo.

### Etapa 6 — Confirmação

A interface apresenta:

- quantidade de arquivos;
- volume total;
- movimentos por grupo;
- caminho de destino calculado para cada arquivo, incluindo diretório raiz,
  grupo e país opcional;
- conflitos;
- alertas;
- arquivos ignorados;
- arquivos que exigem revisão.

O usuário confirma explicitamente.

### Etapa 7 — Execução

O sistema executa uma operação por arquivo, atualizando o diário transacional.

### Etapa 8 — Validação

O sistema valida cada arquivo movido e gera relatório final.

---

## 17. Segurança da movimentação

### 17.1 Princípios

- nunca sobrescrever arquivos silenciosamente;
- não excluir a origem antes de validar a cópia;
- registrar cada etapa;
- permitir retomada;
- tornar a execução idempotente;
- não movimentar arquivos cuja origem mudou depois do plano;
- não executar movimentação durante a fase de análise.

### 17.2 Mesmo volume

Quando origem e destino estiverem no mesmo volume:

1. validar origem;
2. verificar conflito;
3. usar rename/move atômico quando suportado;
4. validar destino;
5. registrar sucesso.

### 17.3 Volumes diferentes

Quando origem e destino estiverem em volumes diferentes:

1. calcular hash da origem;
2. copiar para arquivo temporário no destino;
3. fechar e sincronizar o arquivo;
4. validar tamanho;
5. calcular hash do temporário;
6. comparar hashes;
7. renomear o temporário para o nome final;
8. validar o arquivo final;
9. remover a origem;
10. confirmar que a origem não existe;
11. registrar sucesso.

Nome temporário sugerido:

```text
nome-original.ext.partial-<operation-id>
```

### 17.4 Hash

Utilizar SHA-256.

Modos:

```text
standard:
  - hash obrigatório em cópia entre volumes
  - validação por tamanho em rename no mesmo volume

strict:
  - hash em todos os arquivos
```

### 17.5 Conflitos de nome

Política padrão:

```text
collision_policy: error
```

Outras políticas futuras:

```text
rename_with_suffix
skip
deduplicate_by_hash
```

Nunca utilizar `overwrite` como padrão.

---

## 18. Diário transacional

Cada movimentação deverá possuir:

```text
operation_id
scan_id
file_id
source_path
planned_destination_path
actual_destination_path
source_size
source_hash
destination_size
destination_hash
status
started_at
finished_at
error_code
error_message
```

Estados possíveis:

```text
planned
validating
copying
verifying
renaming
deleting_source
completed
failed
skipped
cancelled
```

A aplicação deverá consultar o diário antes de repetir uma operação.

---

## 19. Relatórios

### 19.1 Relatório de análise

Gerar:

```text
report.html
report.json
report.csv
```

### 19.2 Conteúdo do HTML

- data e hora da análise;
- pasta de origem;
- total de arquivos;
- tamanho total;
- totais por grupo;
- totais por país;
- arquivos de baixa confiança;
- arquivos com erro;
- filtros;
- miniaturas;
- caminho original;
- tipo;
- origem identificada;
- formato;
- modelo do dispositivo;
- data de captura;
- país;
- confiança;
- justificativas;
- classificação manual, quando existente.

### 19.3 Relatório de movimentação

- plano original;
- quantidade planejada;
- quantidade concluída;
- quantidade com falha;
- quantidade ignorada;
- volume movimentado;
- tempo de execução;
- origem e destino de cada arquivo;
- resultado da validação;
- código e mensagem dos erros.

### 19.4 Assets locais

O relatório não deverá depender de:

- fontes externas;
- JavaScript hospedado externamente;
- CDN;
- imagens remotas;
- serviços de mapas.

Miniaturas deverão ser armazenadas em pasta local relativa ao HTML.

---

## 20. Arquitetura recomendada

### 20.1 Estratégia de entrega

Construir em três passos.

#### Passo A — Core Python e CLI

Primeiro desenvolver o motor independente de interface:

```text
scan
extract
classify
geocode
report
plan
execute
validate
```

Isso permite testar a lógica antes de adicionar Next.js.

#### Passo B — API local

Adicionar FastAPI para expor o core.

O serviço deverá escutar somente:

```text
127.0.0.1
```

#### Passo C — Interface

Adicionar Next.js para:

- acompanhar progresso;
- revisar arquivos;
- corrigir classificação;
- configurar destinos;
- aprovar plano;
- acompanhar movimentação.

### 20.2 Seleção de diretórios

Um navegador comum possui restrições para acessar caminhos absolutos e movimentar arquivos arbitrários.

Opções:

1. MVP: campo de caminho + validação no backend.
2. Versão desktop: Tauri com seletor nativo de pastas.
3. Alternativa temporária: diálogo nativo aberto pelo processo Python local.

Recomendação:

```text
MVP técnico: Next.js + FastAPI + caminhos validados
Produto desktop: Tauri + Next.js + FastAPI sidecar
```

### 20.3 Docker

Não utilizar Docker na primeira versão.

Motivos:

- acesso a discos e pastas do Windows fica mais complexo;
- permissões e caminhos se tornam menos intuitivos;
- movimentação entre volumes pode ser dificultada;
- a futura integração CUDA poderá ser avaliada separadamente.

---

## 21. Stack tecnológica

### Backend

```text
Python 3.12 ou 3.13
FastAPI
Pydantic
SQLAlchemy ou SQLModel
SQLite
Jinja2
pathlib
hashlib
shutil
subprocess
```

### Metadados e mídia

```text
ExifTool
FFmpeg
FFprobe
Pillow
pillow-heif
rawpy
```

### Geografia offline

```text
Shapely
GeoPandas opcional
countries.geojson ou countries.gpkg local
```

Para reduzir dependências no MVP, é possível usar Shapely diretamente com um índice espacial.

### Frontend

```text
Next.js
TypeScript
React
TanStack Table
Zod
```

### Desktop futuro

```text
Tauri
```

### Qualidade

```text
pytest
ruff
mypy
pre-commit
Playwright
```

### Gerenciamento de dependências

```text
uv
pnpm
```

Todas as dependências deverão ser fixadas em lockfiles.

---

## 22. Componentes do backend

```text
ScannerService
MetadataExtractor
MediaTypeDetector
ClassificationEngine
IPhoneRule
RawRule
WhatsAppRule
ScreenshotRule
CountryResolver
ThumbnailGenerator
ReportGenerator
DestinationMapper
MovePlanner
MoveExecutor
MoveValidator
JobManager
```

Cada componente deverá ser testável isoladamente.

---

## 23. Estrutura sugerida do repositório

```text
local-media-organizer/
├─ spec.md
├─ README.md
├─ pyproject.toml
├─ uv.lock
├─ .env.example
├─ backend/
│  ├─ app/
│  │  ├─ main.py
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ models/
│  │  ├─ repositories/
│  │  ├─ services/
│  │  │  ├─ scanner.py
│  │  │  ├─ metadata.py
│  │  │  ├─ classifier.py
│  │  │  ├─ geocoder.py
│  │  │  ├─ thumbnails.py
│  │  │  ├─ reports.py
│  │  │  ├─ move_planner.py
│  │  │  ├─ move_executor.py
│  │  │  └─ validator.py
│  │  ├─ rules/
│  │  │  ├─ iphone.py
│  │  │  ├─ whatsapp.py
│  │  │  ├─ screenshot.py
│  │  │  ├─ raw.py
│  │  │  └─ video.py
│  │  └─ templates/
│  ├─ tests/
│  │  ├─ fixtures/
│  │  ├─ unit/
│  │  └─ integration/
│  └─ data/
│     └─ geography/
│        └─ countries.geojson
├─ frontend/
│  ├─ app/
│  ├─ components/
│  ├─ lib/
│  ├─ package.json
│  └─ pnpm-lock.yaml
├─ tools/
│  ├─ exiftool/
│  └─ ffmpeg/
├─ runtime/
│  ├─ database/
│  ├─ reports/
│  ├─ thumbnails/
│  └─ logs/
└─ scripts/
   ├─ dev.ps1
   ├─ test.ps1
   └─ package.ps1
```

---

## 24. Modelo de dados

### 24.1 Scan

```text
id
source_root
recursive
status
total_files
processed_files
total_bytes
created_at
started_at
finished_at
```

### 24.2 MediaFile

```text
id
scan_id
absolute_path
relative_path
file_name
extension
mime_type
file_type
size_bytes
modified_at
created_at
width
height
duration_seconds
metadata_json
processing_status
error_code
error_message
```

### 24.3 Classification

```text
id
media_file_id
media_kind
source_origin
image_format
automatic_routing_group
manual_routing_group
effective_routing_group
confidence
requires_review
reasons_json
device_make
device_model
captured_at
gps_latitude_encrypted_or_hidden
gps_longitude_encrypted_or_hidden
country_code
country_name
```

### 24.4 DestinationRule

```text
id
scan_id
routing_group
destination_root
country_subfolder_enabled
enabled
```

### 24.5 MovePlan

```text
id
scan_id
status
collision_policy
validation_mode
created_at
approved_at
```

### 24.6 MoveOperation

Conforme o diário transacional definido anteriormente.

---

## 25. API inicial

### Scans

```text
POST   /api/scans
GET    /api/scans/{scan_id}
GET    /api/scans/{scan_id}/files
POST   /api/scans/{scan_id}/cancel
```

### Classificação

```text
PATCH  /api/files/{file_id}/classification
GET    /api/files/{file_id}/metadata
GET    /api/files/{file_id}/thumbnail
```

### Destinos e plano

```text
PUT    /api/scans/{scan_id}/destinations
POST   /api/scans/{scan_id}/move-plan
GET    /api/move-plans/{plan_id}
POST   /api/move-plans/{plan_id}/approve
```

### Execução

```text
POST   /api/move-plans/{plan_id}/execute
GET    /api/move-runs/{run_id}
POST   /api/move-runs/{run_id}/cancel
```

### Relatórios

```text
GET    /api/scans/{scan_id}/report
GET    /api/move-runs/{run_id}/report
```

### Progresso

Utilizar Server-Sent Events ou WebSocket:

```text
GET /api/jobs/{job_id}/events
```

---

## 26. Processamento em background

A análise e a movimentação não devem bloquear o servidor HTTP.

Para o MVP:

- utilizar uma fila local simples;
- executar jobs em thread ou processo separado;
- persistir estado no SQLite;
- limitar concorrência de leitura;
- permitir cancelamento entre arquivos;
- não interromper um arquivo no meio da cópia.

Não utilizar Celery ou Redis no MVP.

---

## 27. Política de erros

Cada erro deverá possuir um código estável.

Exemplos:

```text
SOURCE_NOT_FOUND
SOURCE_PERMISSION_DENIED
DESTINATION_PERMISSION_DENIED
UNSUPPORTED_FILE
METADATA_EXTRACTION_FAILED
VIDEO_UNREADABLE
IMAGE_UNREADABLE
GPS_INVALID
COUNTRY_NOT_FOUND
DESTINATION_COLLISION
INSUFFICIENT_DISK_SPACE
SOURCE_CHANGED_AFTER_SCAN
COPY_FAILED
HASH_MISMATCH
DELETE_SOURCE_FAILED
REPORT_GENERATION_FAILED
```

Erros de um arquivo não deverão interromper os demais, exceto quando houver risco sistêmico, como:

- disco cheio;
- banco indisponível;
- pasta de destino removida;
- perda generalizada de permissão.

---

## 28. Privacidade e segurança

- Escutar somente em `127.0.0.1`.
- Não incluir SDK de analytics.
- Não incluir telemetria.
- Não realizar chamadas HTTP externas.
- Não carregar assets externos.
- Não registrar coordenadas em logs comuns.
- Não expor o backend na rede local.
- Não executar comandos montados diretamente com texto do usuário.
- Utilizar listas de argumentos em `subprocess`.
- Normalizar caminhos.
- Bloquear path traversal.
- Não seguir links simbólicos por padrão.
- Não sobrescrever arquivos.
- Não alterar o arquivo de origem durante a análise.
- Reduzir a exposição de metadados sensíveis no HTML.

---

## 29. Requisitos não funcionais

### Confiabilidade

- Nenhum arquivo deve ser removido antes da validação do destino.
- Uma falha deve ser rastreável.
- Operações concluídas não devem ser repetidas.
- O sistema deve recuperar o estado após reinicialização.

### Desempenho

Meta inicial:

- processar ao menos 50.000 registros sem carregar todos os objetos em memória;
- atualizar progresso durante a execução;
- utilizar lotes para ExifTool;
- gerar miniaturas sob demanda ou em fila;
- limitar paralelismo para não saturar o disco.

### Compatibilidade

- Windows 11 como alvo primário.
- Caminhos longos do Windows deverão ser testados.
- Caracteres Unicode deverão ser suportados.
- Linux poderá ser suportado depois.

### Auditabilidade

Toda classificação automática deverá possuir justificativa.

---

## 30. Estratégia de testes

### 30.1 Testes unitários

- regex de WhatsApp;
- identificação de iPhone;
- identificação de RAW;
- prioridade de roteamento;
- validação de GPS;
- point-in-polygon;
- política de conflitos;
- construção de caminho de destino;
- códigos de erro.

### 30.2 Testes de integração

Criar fixtures com:

- JPEG de iPhone com GPS;
- HEIC de iPhone;
- DNG ProRAW;
- MOV de iPhone com GPS;
- screenshot de iPhone;
- screenshot Android;
- imagem WhatsApp;
- vídeo WhatsApp;
- arquivo em pasta `Sent`;
- JPEG sem EXIF;
- RAW de câmera não Apple;
- vídeo corrompido;
- arquivo com extensão incorreta;
- coordenada na fronteira;
- arquivo com nome duplicado;
- arquivo bloqueado;
- origem e destino em volumes diferentes.

### 30.3 Testes de movimentação

Executar em diretórios temporários.

Validar:

- rename no mesmo volume;
- cópia entre volumes simulada;
- falha durante a cópia;
- hash divergente;
- disco insuficiente;
- conflito;
- retomada;
- cancelamento;
- origem alterada depois do plano.

### 30.4 Dataset dourado

Montar um conjunto manualmente rotulado com pelo menos:

```text
100 fotos iPhone
30 iPhone RAW
50 screenshots
50 arquivos WhatsApp
50 vídeos
50 outros arquivos
```

Registrar:

- classe esperada;
- classe prevista;
- confiança;
- falso positivo;
- falso negativo.

A categoria screenshot deverá ser avaliada separadamente por possuir maior ambiguidade.

---

## 31. Critérios de aceite do MVP

O MVP será considerado concluído quando:

1. analisar uma pasta recursivamente;
2. identificar tipos de mídia;
3. identificar iPhone com base em metadados;
4. separar iPhone RAW;
5. identificar WhatsApp com regras documentadas;
6. identificar screenshots com confiança;
7. identificar país por GPS sem internet;
8. gerar HTML local;
9. permitir revisão e override;
10. permitir configurar destinos;
11. gerar dry run;
12. bloquear sobrescrita;
13. mover com diário transacional;
14. validar tamanho e hash conforme o modo;
15. produzir relatório de erros;
16. retomar uma execução interrompida;
17. concluir testes de integração principais.

---

## 32. Roadmap inicial

### Fase 0 — Bootstrap

- criar repositório;
- configurar Python, `uv`, lint e testes;
- adicionar ExifTool e FFmpeg;
- criar banco SQLite;
- criar fixtures iniciais.

### Fase 1 — Inventário e metadados

- scanner;
- detector de tipo;
- ExifTool em lote;
- FFprobe;
- persistência;
- CLI de análise.

Comando esperado:

```bash
media-organizer scan "D:\Fotos" --recursive
```

### Fase 2 — Classificação e país

- regras de vídeo;
- regra iPhone;
- regra RAW;
- regra WhatsApp;
- regra screenshot;
- pontuação;
- geocodificação offline;
- overrides via CLI.

### Fase 3 — Relatório estático

- miniaturas;
- HTML;
- JSON;
- CSV;
- filtros básicos.

### Fase 4 — FastAPI

- endpoints;
- jobs;
- progresso;
- relatórios;
- documentação local da API.

### Fase 5 — Next.js

- dashboard;
- tabela;
- filtros;
- revisão;
- configuração de destinos;
- dry run;
- execução;
- relatório final.

### Fase 6 — Empacotamento desktop

- Tauri;
- seletor nativo;
- inicialização automática do backend;
- instalador;
- atualização manual/offline.

---

## 33. Expansão futura com IA local

A RTX 4090 possui capacidade adequada para processar embeddings de imagens, gerar descrições, realizar OCR e executar modelos multimodais locais.

A arquitetura futura deverá separar quatro tarefas.

### 33.1 Embeddings e busca semântica

Objetivo:

- transformar imagens em vetores;
- buscar por texto;
- agrupar fotos semelhantes;
- encontrar fotos de praia, montanha, documentos, comida, animais etc.;
- identificar conteúdo visual aproximado.

Modelos candidatos:

```text
SigLIP 2
Qwen3-VL-Embedding-2B
Qwen3-VL-Embedding-8B
```

Recomendação inicial:

```text
SigLIP 2 So400m ou Qwen3-VL-Embedding-2B
```

Motivo:

- boa relação entre qualidade, velocidade e consumo de VRAM;
- adequados para indexação em lote;
- permitem busca imagem-texto;
- o modelo de 2B deixa mais margem de memória para processamento e aplicação.

Persistência dos vetores:

```text
FAISS local
ou
SQLite com extensão vetorial
ou
LanceDB local
```

Para o primeiro protótipo, utilizar FAISS local.

### 33.2 Descrição, tags, OCR e entendimento

Modelos candidatos:

```text
Qwen3-VL-2B-Instruct
Qwen3-VL-8B-Instruct
```

Recomendação:

```text
Qwen3-VL-2B para processamento em massa
Qwen3-VL-8B quantizado em 4 bits para maior qualidade
```

O modelo maior poderá ser usado somente nos arquivos selecionados ou quando o modelo menor tiver baixa confiança.

Saída estruturada sugerida:

```json
{
  "caption": "Duas pessoas caminhando em uma rua histórica",
  "objects": ["person", "street", "building"],
  "scene": "urban",
  "activities": ["walking"],
  "visible_text": [],
  "safety_labels": [],
  "confidence": 0.88
}
```

### 33.3 Detecção e segmentação

Para detectar objetos ou criar caixas e máscaras:

- utilizar modelos de object detection;
- avaliar modelos disponíveis no NVIDIA TAO;
- utilizar modelos open-vocabulary quando as categorias não forem fixas;
- adicionar segmentação somente quando houver um caso de uso claro.

### 33.4 Vídeo

Para vídeos:

1. extrair metadados;
2. amostrar frames;
3. detectar mudanças de cena;
4. gerar embeddings dos frames;
5. agregar resultados;
6. opcionalmente executar um VLM em frames representativos.

Não executar um VLM em todos os frames.

Estratégia inicial:

```text
1 frame a cada N segundos
+
detecção de mudança de cena
+
limite máximo de frames por vídeo
```

---

## 34. Bibliotecas NVIDIA recomendadas para a fase de IA

### 34.1 PyTorch com CUDA

Utilizar como primeira opção de desenvolvimento e experimentação.

Vantagens:

- integração direta com os modelos;
- bom suporte para RTX;
- menor complexidade inicial;
- permite validar qualidade antes de otimizar.

### 34.2 TensorRT for RTX

Utilizar depois que o modelo estiver estável.

Objetivo:

- reduzir latência;
- aumentar throughput;
- otimizar inferência;
- executar modelos ONNX ou integrações compatíveis em GPUs RTX.

É a opção NVIDIA mais alinhada a uma aplicação local Windows com RTX 4090.

### 34.3 NVIDIA DALI

Útil para:

- leitura em lote;
- decode;
- resize;
- crop;
- pré-processamento na GPU.

Observação:

- é mais simples em Linux;
- no Windows, considerar WSL;
- não é necessária no MVP de metadados;
- deverá ser adicionada apenas se o carregamento de imagens se tornar gargalo.

### 34.4 nvImageCodec e CV-CUDA

Úteis para acelerar:

- decode;
- encode;
- resize;
- conversões;
- pré e pós-processamento.

Aplicar quando houver grande volume e o pipeline Python/Pillow se tornar gargalo.

### 34.5 NVIDIA DeepStream

Indicado para:

- streams de vídeo;
- múltiplas câmeras;
- vídeo em tempo real;
- tracking;
- pipelines GStreamer.

Para uma pasta de arquivos processada em lote, DeepStream provavelmente será excessivo no início.

### 34.6 NVIDIA TAO Toolkit

Indicado quando for necessário:

- fine-tuning;
- classificação customizada;
- object detection;
- segmentação;
- adaptação de VLM;
- exportação para ONNX e implantação otimizada.

Não utilizar antes de existir um dataset rotulado e uma métrica clara.

---

## 35. Arquitetura futura de IA

```text
Media Scanner
    ↓
Metadata Classifier
    ↓
Thumbnail / Frame Extractor
    ↓
Embedding Model
    ↓
Vector Index
    ↓
Optional VLM Enrichment
    ↓
Structured Metadata
    ↓
Search and Album UI
```

Princípio:

```text
modelo leve para todos os arquivos
modelo maior somente quando necessário
```

Isso reduz tempo, uso de VRAM e consumo de energia.

---

## 36. Decisões técnicas recomendadas

1. Começar pelo core Python, sem interface.
2. Utilizar ExifTool como fonte principal de metadados.
3. Utilizar classificação multidimensional.
4. Manter regras explicáveis.
5. Utilizar base local de polígonos para país.
6. Gerar relatório HTML antes de criar o frontend completo.
7. Implementar dry run antes de qualquer movimentação.
8. Nunca sobrescrever por padrão.
9. Utilizar diário transacional em SQLite.
10. Usar Tauri somente depois que o fluxo estiver validado.
11. Não utilizar GPU no MVP de metadados.
12. Começar a fase de IA com embeddings.
13. Usar VLM maior apenas como segunda etapa.
14. Avaliar TensorRT for RTX depois de medir o pipeline PyTorch.
15. Não adotar DeepStream para processamento em lote sem necessidade comprovada.

---

## 37. Primeira história de usuário a implementar

### US-001 — Analisar uma pasta e gerar inventário

**Como** usuário  
**Quero** informar uma pasta local  
**Para** receber um inventário de imagens e vídeos sem modificar os arquivos  

### Critérios de aceite

- aceita caminho local;
- valida existência;
- percorre subpastas;
- identifica tipo;
- extrai metadados;
- persiste no SQLite;
- mostra progresso;
- registra erros;
- gera JSON;
- não move, altera ou exclui arquivos.

### Comando inicial

```bash
media-organizer scan "D:\Fotos" \
  --recursive \
  --output ".\runtime\reports\scan-001"
```

---

## 38. Segunda história de usuário

### US-002 — Classificar o inventário

**Como** usuário  
**Quero** classificar os arquivos analisados  
**Para** revisar os grupos antes de organizar minhas pastas  

### Critérios de aceite

- classifica vídeo;
- classifica screenshot;
- classifica WhatsApp;
- identifica iPhone;
- separa iPhone RAW;
- identifica país por GPS;
- mostra confiança;
- mostra justificativa;
- não move arquivos.

---

## 39. Terceira história de usuário

### US-003 — Gerar plano de movimentação

**Como** usuário  
**Quero** definir um destino para cada grupo  
**Para** visualizar exatamente o que será movido antes de confirmar  

### Critérios de aceite

- permite definir os destinos;
- valida permissões;
- valida espaço;
- detecta conflitos;
- apresenta origem e destino;
- calcula volume;
- gera dry run;
- não executa automaticamente.

---

## 40. Quarta história de usuário

### US-004 — Executar e validar a movimentação

**Como** usuário  
**Quero** aprovar o plano  
**Para** mover os arquivos com segurança e receber um relatório completo  

### Critérios de aceite

- exige confirmação;
- registra cada operação;
- não sobrescreve;
- valida arquivos;
- permite retomada;
- mostra progresso;
- registra falhas;
- gera relatório final.

---

## 41. Questões a decidir após o primeiro protótipo

1. Vídeos do WhatsApp deverão continuar em `video` ou terão grupo próprio?
2. O usuário deseja criar subpastas por país?
3. O país deverá usar nome em português, inglês ou código ISO?
4. Arquivos enviados pelo WhatsApp deverão ser ignorados ou organizados separadamente?
5. Screenshots de computador também entrarão no grupo de screenshots?
6. Arquivos sem metadados deverão passar por análise visual futura?
7. O modo padrão de validação será `standard` ou `strict`?
8. Colisões deverão gerar erro ou sufixo automático?
9. O HTML deverá ser totalmente portátil ou depender do backend local?
10. O sistema deverá permitir copiar, além de mover?

---

## 42. Referências técnicas a consultar durante a implementação

Documentação oficial recomendada:

- ExifTool e tabelas de tags EXIF/QuickTime.
- Apple ProRAW.
- Python `pathlib`, `shutil` e `hashlib`.
- FFmpeg e FFprobe.
- FastAPI.
- Shapely.
- NVIDIA PyTorch/CUDA.
- NVIDIA TensorRT for RTX.
- NVIDIA DALI.
- NVIDIA nvImageCodec.
- NVIDIA CV-CUDA.
- NVIDIA DeepStream.
- NVIDIA TAO Toolkit.
- Qwen3-VL.
- Qwen3-VL-Embedding.
- SigLIP 2.

---

## 43. Resultado esperado da primeira entrega

A primeira entrega não precisa possuir Next.js.

Ela deverá produzir:

```text
1. banco SQLite com o inventário;
2. JSON com metadados normalizados;
3. CSV resumido;
4. HTML com classificação e miniaturas;
5. log de erros;
6. nenhuma alteração nos arquivos originais.
```

Somente depois dessa entrega estar validada deverá começar a funcionalidade de movimentação.
